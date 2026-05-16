import io
import base64
import queue
import threading
import numpy as np
import requests
import os
import json
import websocket as ws_client
import time
from datetime import datetime, timedelta
from collections import Counter
from PIL import Image
from ultralytics import YOLO
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kacamata_tunanetra_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ================= KONFIGURASI =================
IP_KAMERA     = os.getenv('IP_KAMERA', '192.168.137.244')
URL_KAMERA    = f'http://{IP_KAMERA}:81/stream'
URL_WEBSOCKET = f'ws://{IP_KAMERA}:82'
CONF_THRESH   = 0.6
JARAK_BAHAYA  = 80

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ===============================================

# Shared state
frame_queue    = queue.Queue(maxsize=1)
stop_event     = threading.Event()
jarak_saat_ini = 999
jarak_lock     = threading.Lock()
model          = None
sesi_id        = None
_last_simpan   = {}

# ============================================================
# DATABASE
# ============================================================
def mulai_sesi():
    global sesi_id
    try:
        result  = supabase.table('sesi').insert({'total_deteksi': 0}).execute()
        sesi_id = result.data[0]['id']
        print(f"[DB] Sesi dimulai: ID {sesi_id}")
    except Exception as e:
        print(f"[DB] Gagal mulai sesi: {e}")

def simpan_deteksi(objek, confidence, jarak, peringatan, is_bahaya):
    try:
        supabase.table('deteksi_log').insert({
            'objek'      : objek,
            'confidence' : confidence,
            'jarak'      : jarak,
            'peringatan' : peringatan,
            'is_bahaya'  : is_bahaya
        }).execute()
    except Exception as e:
        print(f"[DB] Gagal simpan deteksi: {e}")

def ambil_riwayat(limit=50):
    try:
        result = supabase.table('deteksi_log')\
            .select('*')\
            .order('waktu', desc=True)\
            .limit(limit)\
            .execute()
        return result.data
    except Exception as e:
        print(f"[DB] Gagal ambil riwayat: {e}")
        return []

def ambil_statistik():
    try:
        result = supabase.table('deteksi_log').select('objek').execute()
        stats  = {}
        for row in result.data:
            objek        = row['objek']
            stats[objek] = stats.get(objek, 0) + 1
        return stats
    except Exception as e:
        print(f"[DB] Gagal ambil statistik: {e}")
        return {}

# ============================================================
# PREDIKSI
# ============================================================
def hitung_prediksi():
    try:
        result = supabase.table('deteksi_log').select('*').execute()
        data   = result.data

        if len(data) < 5:
            return None

        # 1. Jam paling berbahaya
        jam_bahaya        = [r['jam'] for r in data if r.get('is_bahaya') and r.get('jam') is not None]
        jam_counter       = Counter(jam_bahaya)
        jam_paling_bahaya = jam_counter.most_common(3)

        # 2. Objek paling sering
        semua_objek    = [r['objek'] for r in data if r.get('objek')]
        objek_counter  = Counter(semua_objek)
        objek_terbanyak = objek_counter.most_common(5)

        # 3. Tren 7 hari
        tujuh_hari_lalu = (datetime.now() - timedelta(days=7)).isoformat()
        data_minggu     = [r for r in data if r.get('waktu', '') > tujuh_hari_lalu]
        tren_harian     = {}
        for r in data_minggu:
            if r.get('waktu'):
                tanggal              = r['waktu'][:10]
                tren_harian[tanggal] = tren_harian.get(tanggal, 0) + 1

        # 4. Risiko jam sekarang
        jam_sekarang   = datetime.now().hour
        total_jam_ini  = len([r for r in data if r.get('jam') == jam_sekarang])
        bahaya_jam_ini = len([r for r in data if r.get('jam') == jam_sekarang and r.get('is_bahaya')])
        risiko_persen  = round((bahaya_jam_ini / total_jam_ini) * 100) if total_jam_ini > 0 else 0

        # 5. Prediksi objek jam ini
        objek_jam_ini   = [r['objek'] for r in data if r.get('jam') == jam_sekarang and r.get('objek')]
        prediksi_objek  = Counter(objek_jam_ini).most_common(3)

        # 6. Tingkat keamanan
        total        = len(data)
        total_bahaya = len([r for r in data if r.get('is_bahaya')])
        persen_aman  = round(((total - total_bahaya) / total) * 100) if total > 0 else 100

        hasil = {
            'jam_paling_bahaya'      : [{'jam': j, 'frekuensi': f} for j, f in jam_paling_bahaya],
            'objek_terbanyak'        : [{'objek': o, 'total': t} for o, t in objek_terbanyak],
            'tren_harian'            : [{'tanggal': t, 'total': j} for t, j in sorted(tren_harian.items())],
            'risiko_jam_ini'         : {
                'jam'    : jam_sekarang,
                'persen' : risiko_persen,
                'level'  : 'Tinggi' if risiko_persen > 60 else 'Sedang' if risiko_persen > 30 else 'Rendah'
            },
            'prediksi_objek_jam_ini' : [{'objek': o, 'kemungkinan': t} for o, t in prediksi_objek],
            'tingkat_keamanan'       : persen_aman,
            'total_data'             : total,
            'diupdate'               : datetime.now().isoformat()
        }

        # Simpan ke cache
        supabase.table('prediksi_cache').upsert({
            'tipe'     : 'analisis_utama',
            'data'     : hasil,
            'diupdate' : datetime.now().isoformat()
        }).execute()

        return hasil

    except Exception as e:
        print(f"[PREDIKSI] Error: {e}")
        return None

def update_prediksi_background():
    while not stop_event.is_set():
        hitung_prediksi()
        time.sleep(300)

# ============================================================
# THREAD 1: Kamera
# ============================================================
def thread_kamera():
    while not stop_event.is_set():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            stream  = requests.get(URL_KAMERA, stream=True, timeout=10, headers=headers)
            buf     = b''

            for chunk in stream.iter_content(chunk_size=4096):
                if stop_event.is_set():
                    break
                buf += chunk
                a = buf.find(b'\xff\xd8')
                b = buf.find(b'\xff\xd9')
                if a != -1 and b != -1 and b > a:
                    jpg = buf[a:b+2]
                    buf = buf[b+2:]
                    try:
                        img   = Image.open(io.BytesIO(jpg)).convert('RGB')
                        frame = np.array(img)
                        if frame_queue.full():
                            try: frame_queue.get_nowait()
                            except queue.Empty: pass
                        frame_queue.put_nowait(frame)
                    except Exception:
                        pass
            stream.close()

        except Exception as e:
            print(f"[KAMERA] Reconnecting... ({e})")
            time.sleep(2)

# ============================================================
# THREAD 2: YOLO + Broadcast + Simpan DB
# ============================================================
def thread_yolo_and_broadcast():
    global jarak_saat_ini

    while not stop_event.is_set():
        try:
            frame = frame_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        results       = model(frame, conf=CONF_THRESH, verbose=False)
        annotated     = results[0].plot()
        annotated_rgb = annotated[:, :, ::-1]

        img = Image.fromarray(annotated_rgb)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        frame_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        deteksi_list = []
        peringatan   = []

        with jarak_lock:
            jarak = jarak_saat_ini

        for box in results[0].boxes:
            nama       = model.names[int(box.cls[0])]
            conf       = float(box.conf[0])
            nama_lower = nama.lower()

            deteksi_list.append({
                'nama': nama,
                'conf': round(conf * 100, 1)
            })

            is_pohon = 'tree'   in nama_lower
            is_orang = 'people' in nama_lower or 'person' in nama_lower
            is_uang  = any(n in nama_lower for n in
                          ['1000','2000','5000','10000','20000','50000','100000'])

            if jarak < JARAK_BAHAYA:
                if is_pohon:
                    peringatan.append("Awas, ada pohon di depan")
                elif is_orang:
                    peringatan.append("Awas, ada orang di depan")
            if is_uang:
                nominal = ''.join(filter(str.isdigit, nama_lower))
                peringatan.append(f"Uang {nominal} rupiah terdeteksi")

            # Simpan ke DB dengan cooldown 5 detik per objek
            now = time.time()
            if now - _last_simpan.get(nama, 0) > 5.0:
                _last_simpan[nama] = now
                threading.Thread(
                    target=simpan_deteksi,
                    args=(nama, round(conf*100,1), jarak,
                          ', '.join(peringatan), jarak < JARAK_BAHAYA),
                    daemon=True
                ).start()

        socketio.emit('update', {
            'frame'     : frame_b64,
            'jarak'     : jarak,
            'deteksi'   : deteksi_list,
            'peringatan': list(set(peringatan)),
            'bahaya'    : jarak < JARAK_BAHAYA
        })

# ============================================================
# THREAD 3: Sensor WebSocket
# ============================================================
def thread_sensor():
    global jarak_saat_ini

    def on_message(ws, message):
        global jarak_saat_ini
        if message.strip().isdigit():
            with jarak_lock:
                jarak_saat_ini = int(message.strip())

    def on_open(ws):
        print("[SENSOR] WebSocket terhubung!")

    def on_error(ws, error):
        print(f"[SENSOR] Error: {error}")

    def on_close(ws, code, msg):
        print("[SENSOR] Terputus, reconnecting...")

    while not stop_event.is_set():
        try:
            ws = ws_client.WebSocketApp(
                f'ws://{IP_KAMERA}:82',
                on_message=on_message,
                on_open=on_open,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(ping_interval=5, ping_timeout=3)
        except Exception as e:
            print(f"[SENSOR] Reconnecting... ({e})")
        time.sleep(2)

# ============================================================
# ROUTES
# ============================================================
@app.route('/upload_frame', methods=['POST'])
def upload_frame():
    global jarak_saat_ini
    try:
        # Ambil data jarak dari URL (contoh: /upload_frame?jarak=45)
        jarak_param = request.args.get('jarak')
        if jarak_param and jarak_param.lstrip('-').isdigit():
            with jarak_lock:
                jarak_saat_ini = int(jarak_param)

        # Ambil file gambar murni dari body request
        img_bytes = request.data
        if not img_bytes:
            return jsonify({'error': 'Tidak ada gambar'}), 400

        # Konversi byte gambar menjadi array untuk YOLO
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        frame = np.array(img)

        # Masukkan ke antrean agar diproses oleh thread YOLO
        if frame_queue.full():
            try: frame_queue.get_nowait()
            except queue.Empty: pass
        frame_queue.put_nowait(frame)

        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f"[UPLOAD ERROR] {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_ip', methods=['POST'])
def update_ip():
    global IP_KAMERA, URL_KAMERA, URL_WEBSOCKET
    ip_baru = request.json.get('ip')
    if ip_baru:
        IP_KAMERA     = ip_baru
        URL_KAMERA    = f'http://{ip_baru}:81/stream'
        URL_WEBSOCKET = f'ws://{ip_baru}:82'
        return {'status': 'ok', 'ip': ip_baru}
    return {'status': 'error'}, 400

@app.route('/api/riwayat')
def api_riwayat():
    limit = request.args.get('limit', 50, type=int)
    data  = ambil_riwayat(limit=limit)
    return jsonify(data)

@app.route('/api/statistik')
def api_statistik():
    return jsonify(ambil_statistik())

@app.route('/api/prediksi')
def api_prediksi():
    try:
        cache = supabase.table('prediksi_cache')\
            .select('*')\
            .eq('tipe', 'analisis_utama')\
            .execute()
        if cache.data:
            return jsonify(cache.data[0]['data'])
    except Exception:
        pass

    hasil = hitung_prediksi()
    if hasil:
        return jsonify(hasil)
    return jsonify({'error': 'Data belum cukup untuk prediksi'}), 404

@app.route('/api/prediksi/risiko_sekarang')
def api_risiko_sekarang():
    try:
        jam_sekarang = datetime.now().hour
        result       = supabase.table('deteksi_log')\
            .select('is_bahaya')\
            .eq('jam', jam_sekarang)\
            .execute()
        data         = result.data
        total        = len(data)
        total_bahaya = len([r for r in data if r.get('is_bahaya')])
        persen       = round((total_bahaya / total) * 100) if total > 0 else 0
        return jsonify({
            'jam'        : jam_sekarang,
            'persen'     : persen,
            'level'      : 'Tinggi' if persen > 60 else 'Sedang' if persen > 30 else 'Rendah',
            'total_data' : total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def on_connect():
    print(f"[WEB] Browser terhubung: {request.sid}")
    emit('status', {'message': 'Terhubung ke server Kacamata AI'})

@socketio.on('disconnect')
def on_disconnect():
    print(f"[WEB] Browser terputus: {request.sid}")

# ============================================================
# MAIN
# ============================================================
def start_background_threads():
    global model
    print("[INFO] Memuat model YOLO...")
    model = YOLO('best.pt')
    print("[INFO] Model siap!")

    mulai_sesi()

    threads = [
        threading.Thread(target=thread_yolo_and_broadcast,  daemon=True),
        threading.Thread(target=update_prediksi_background, daemon=True),
    ]
    for t in threads:
        t.start()

if __name__ == '__main__':
    start_background_threads()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
