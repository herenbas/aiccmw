import io
import wave
import sounddevice as sd

import numpy as np
from flask import Flask, request, jsonify, send_file
import sqlite3
import os
import requests
import base64
from datetime import datetime

app = Flask(__name__)
API_SEND_URL = "https://example.com/send_audio"  # Gönderilecek API URL'si
API_RESPONSE_URL = "https://example.com/send_response"  # Gelen sesin iletileceği API URL'si
conn = sqlite3.connect("audio.db", check_same_thread=False)
cursor = conn.cursor()

# SQLite Veritabanı Bağlantısı
def get_db_connection():
    conn = sqlite3.connect("audio.db")
    conn.row_factory = sqlite3.Row
    return conn

#ok
# Veritabanını oluştur
with get_db_connection() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS audio_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file BLOB,
                    received_at TEXT,
                    file_id TEXT
                )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS audio_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT,
                    response_file BLOB,
                    received_at TEXT
                )''')
    conn.commit()


# Ses Dosyası Alma ve Kaydetme
@app.route("/sorualkaydet", methods=["POST"])
def upload_audio():
    data = request.json
    file_base64 = data.get("file")
    file_id = data.get("file_id")  # GUID oluşturuluyor
    print(file_id)

    if not file_base64:
        return jsonify({"error": "No file provided"}), 400

    file_bytes = base64.b64decode(file_base64)
    received_at = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.execute("INSERT INTO audio_requests (file, received_at, file_id) VALUES (?, ?, ?)",
                              (file_bytes, received_at, file_id))
        request_id = cursor.lastrowid
        conn.commit()

    # API'ye Base64 olarak gönderme
    #response = requests.post(API_SEND_URL, json={"file": file_base64, "file_id": file_id, "received_at": received_at})

    return jsonify({"id": request_id, "file_id": file_id})#, "status": response.status_code})


# API'den Gelen Yanıtı Kaydetme
@app.route("/cevapalkaydet", methods=["POST"])
def receive_audio():
    data = request.json
    file_id = data.get("file_id")
    response_file_base64 = data.get("file")

    if not file_id or not response_file_base64:
        return jsonify({"error": "Missing data"}), 400

    response_file_bytes = base64.b64decode(response_file_base64)
    received_at = datetime.now().isoformat()

    with get_db_connection() as conn:
        conn.execute("INSERT INTO audio_responses (file_id,response_file, received_at) VALUES (?, ?, ?)",
                     (file_id, response_file_bytes, received_at))
        conn.commit()

    # Gelen yanıtı başka API'ye iletme
    #requests.post(API_RESPONSE_URL, json={"file": response_file_base64, "id": request_id})

    return jsonify({"id": file_id, "status": "saved"})


# Kaydedilen Sesleri Getirme
@app.route("/play_saved/<int:audio_id>", methods=["GET"])
def play_saved_audio(audio_id):
    cursor.execute("SELECT file FROM audio_requests WHERE id = ?", (audio_id,))
    result = cursor.fetchone()
    if not result:
        return jsonify({"error": "Audio not found"}), 404

    audio_bytes = result[0]
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

    sd.play(audio_data, samplerate=sample_rate)
    return jsonify({"status": "success", "message": "Playing saved audio"})


# Kaydedilen Cevap Seslerini Getirme
@app.route("/get_response/<int:request_id>", methods=["GET"])
def get_response(request_id):
    with get_db_connection() as conn:
        row = conn.execute("SELECT response_file FROM audio_responses WHERE id = ?", (request_id,)).fetchone()
    if row:
        return send_file(row["response_file"], as_attachment=True)
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    app.run(host="192.168.1.7",port=8004,debug=True)
