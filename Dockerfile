# Menggunakan Python 3.11 versi ringan yang stabil
FROM python:3.11-slim

# Mengambil alih OS dan menginstal library grafis C++ secara paksa
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Menentukan folder kerja di dalam server
WORKDIR /app

# Menyalin requirements dan menginstal library Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Menghapus versi OpenCV bawaan Ultralytics dan memaksa pakai versi headless
RUN pip uninstall -y opencv-python && pip install opencv-python-headless==4.9.0.80

# Menyalin seluruh kode aplikasi dan model YOLO kamu
COPY . .

# Menjalankan server Gunicorn dengan worker eventlet
CMD gunicorn app:app -b 0.0.0.0:$PORT -k eventlet