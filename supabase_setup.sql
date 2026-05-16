-- ============================================================
-- Jalankan SQL ini di Supabase SQL Editor
-- Project: KacamataPintar
-- ============================================================

-- Tabel log deteksi
CREATE TABLE IF NOT EXISTS deteksi_log (
    id          SERIAL PRIMARY KEY,
    waktu       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    objek       VARCHAR(200) NOT NULL,
    confidence  FLOAT,
    jarak       INTEGER,
    peringatan  TEXT,
    is_bahaya   BOOLEAN DEFAULT FALSE,
    jam         INTEGER,
    hari_minggu INTEGER
);

-- Tabel sesi pengguna
CREATE TABLE IF NOT EXISTS sesi (
    id            SERIAL PRIMARY KEY,
    mulai         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    selesai       TIMESTAMP WITH TIME ZONE,
    total_deteksi INTEGER DEFAULT 0
);

-- Tabel cache prediksi
CREATE TABLE IF NOT EXISTS prediksi_cache (
    id        SERIAL PRIMARY KEY,
    tipe      VARCHAR(50) UNIQUE,
    data      JSONB,
    diupdate  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger: isi jam & hari_minggu otomatis saat insert
CREATE OR REPLACE FUNCTION set_waktu_info()
RETURNS TRIGGER AS $$
BEGIN
    NEW.jam         = EXTRACT(HOUR FROM NEW.waktu);
    NEW.hari_minggu = EXTRACT(DOW  FROM NEW.waktu);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_waktu_info ON deteksi_log;
CREATE TRIGGER trigger_waktu_info
BEFORE INSERT ON deteksi_log
FOR EACH ROW EXECUTE FUNCTION set_waktu_info();

-- Index untuk query lebih cepat
CREATE INDEX IF NOT EXISTS idx_deteksi_waktu   ON deteksi_log(waktu DESC);
CREATE INDEX IF NOT EXISTS idx_deteksi_jam     ON deteksi_log(jam);
CREATE INDEX IF NOT EXISTS idx_deteksi_objek   ON deteksi_log(objek);
CREATE INDEX IF NOT EXISTS idx_deteksi_bahaya  ON deteksi_log(is_bahaya);
