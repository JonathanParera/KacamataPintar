# Kacamata AI — Sistem Bantu Tunanetra

Sistem deteksi objek real-time untuk tunanetra menggunakan ESP32-CAM,
sensor ultrasonik, YOLOv8, dan web dashboard dengan prediksi berbasis data.

---

## Struktur Folder

```
KacamataPintar/          ← Backend Python (deploy ke Railway/VPS)
├── app.py               ← Server utama Flask + YOLO + WebSocket
├── requirements.txt     ← Library Python
├── Procfile             ← Konfigurasi server
├── .env.example         ← Contoh environment variable
├── .gitignore           ← File yang tidak diupload ke GitHub
├── supabase_setup.sql   ← SQL untuk setup database
└── templates/
    └── index.html       ← Halaman live feed (HP pengguna)

KacamataPintar-Frontend/ ← Frontend (deploy ke Vercel)
├── index.html           ← Dashboard prediksi & monitoring dosen
└── vercel.json          ← Konfigurasi Vercel
```

---

## Arsitektur Sistem

```
ESP32-CAM + Sensor
      │
      │ WiFi (stream + WebSocket)
      ▼
Railway/VPS (Python Backend)
  ├── Flask + Socket.IO
  ├── YOLOv8 (deteksi objek)
  ├── Analisis & Prediksi
  └── Supabase (simpan log)
      │
      ├── WebSocket ──▶ HP Pengguna (live feed + suara)
      ├── API      ──▶ Vercel (dashboard prediksi dosen)
      └── Database ──▶ Supabase (riwayat + statistik)
```

---

## Langkah Setup

### 1. Supabase (Database)

1. Daftar di supabase.com
2. Buat project baru
3. Buka SQL Editor
4. Jalankan isi file `supabase_setup.sql`
5. Catat Project URL dan anon key dari Settings → API

### 2. Backend (Railway atau VPS)

**Buat file .env dari .env.example:**
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyxxxxxx...
IP_KAMERA=192.168.137.182
```

**Upload ke GitHub:**
```bash
git init
git add app.py requirements.txt Procfile .env.example supabase_setup.sql templates/
git commit -m "Kacamata AI Backend"
git push origin main
```

**Upload best.pt via Railway CLI:**
```bash
railway login
railway link
railway up
```

**Environment variables di Railway:**
- SUPABASE_URL
- SUPABASE_KEY
- IP_KAMERA

### 3. Frontend (Vercel)

1. Edit `KacamataPintar-Frontend/index.html`
2. Ganti `GANTI_URL_RAILWAY` dengan URL Railway kamu
3. Upload ke GitHub (repo terpisah)
4. Deploy ke Vercel

**Edit `templates/index.html` juga:**
- Ganti `GANTI_URL_VERCEL` dengan URL Vercel kamu

---

## Environment Variables

| Variable       | Keterangan                        |
|----------------|-----------------------------------|
| SUPABASE_URL   | URL project Supabase              |
| SUPABASE_KEY   | Anon key Supabase                 |
| IP_KAMERA      | IP ESP32-CAM (default: 192.168.x) |

---

## API Endpoints

| Endpoint                    | Method | Keterangan                    |
|-----------------------------|--------|-------------------------------|
| `/`                         | GET    | Halaman live feed             |
| `/api/riwayat`              | GET    | Riwayat deteksi dari DB       |
| `/api/statistik`            | GET    | Statistik per objek           |
| `/api/prediksi`             | GET    | Hasil analisis & prediksi     |
| `/api/prediksi/risiko_sekarang` | GET | Risiko untuk jam ini      |
| `/update_ip`                | POST   | Update IP ESP32               |

---

## Teknologi yang Digunakan

| Komponen    | Teknologi                        |
|-------------|----------------------------------|
| Hardware    | ESP32-CAM + HC-SR04              |
| AI Model    | YOLOv8n (Ultralytics)            |
| Backend     | Python, Flask, Socket.IO         |
| Database    | Supabase (PostgreSQL)            |
| Frontend    | HTML, JavaScript, Chart.js       |
| Hosting BE  | Railway / VPS                    |
| Hosting FE  | Vercel                           |
| Komunikasi  | WebSocket, HTTP REST API         |
| TTS         | Web Speech API (browser)         |
