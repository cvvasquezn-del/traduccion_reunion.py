import os
import time

import sounddevice as sd
import soundfile as sf
import requests
from dotenv import load_dotenv

# =========================
# Configuración general
# =========================

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

if not ASSEMBLYAI_API_KEY or not DEEPL_API_KEY:
    raise RuntimeError(
        "Faltan ASSEMBLYAI_API_KEY o DEEPL_API_KEY en el archivo .env"
    )

SAMPLE_RATE = 16000       # Hz
CHANNELS = 1              # mono
DURATION_SECONDS = 8      # segundos por fragmento (ajusta si quieres)


# =========================
# Funciones auxiliares
# =========================

def record_audio(filename: str, duration: int = DURATION_SECONDS) -> None:
    """Graba audio desde el dispositivo de entrada por defecto y lo guarda como WAV."""
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()
    sf.write(filename, recording, SAMPLE_RATE)


def upload_to_assemblyai(filename: str) -> str:
    """Sube el archivo de audio a AssemblyAI y devuelve la URL de subida."""
    url = "https://api.assemblyai.com/v2/upload"
    headers = {"authorization": ASSEMBLYAI_API_KEY}

    def read_file(fname, chunk_size: int = 5_242_880):
        with open(fname, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                yield data

    response = requests.post(url, headers=headers, data=read_file(filename))
    response.raise_for_status()
    data = response.json()
    return data["upload_url"]


def transcribe_with_assemblyai(audio_url: str) -> str:
    """Solicita la transcripción a AssemblyAI y espera hasta obtener el texto."""
    endpoint = "https://api.assemblyai.com/v2/transcript"
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "audio_url": audio_url,
        "language_code": "en",  # origen: inglés
    }

    # Crear la transcripción
    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()
    transcript_id = response.json()["id"]

    # Hacer polling hasta que termine
    poll_url = f"{endpoint}/{transcript_id}"

    while True:
        poll_res = requests.get(poll_url, headers=headers)
        poll_res.raise_for_status()
        poll_data = poll_res.json()
        status = poll_data["status"]

        if status == "completed":
            return poll_data.get("text", "") or ""
        elif status == "error":
            error_msg = poll_data.get("error", "Error desconocido")
            raise RuntimeError(f"Error en AssemblyAI: {error_msg}")
        else:
            # queued / processing
            time.sleep(1)


def translate_with_deepl(text_en: str) -> str:
    """Traduce texto EN -> ES usando DeepL API Free."""
    if not text_en.strip():
        return ""

    url = "https://api-free.deepl.com/v2/translate"
    data = {
        "auth_key": DEEPL_API_KEY,
        "text": text_en,
        "source_lang": "EN",
        "target_lang": "ES",
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    res_json = response.json()
    translations = res_json.get("translations", [])
    if not translations:
        return ""

    return translations[0]["text"]


# =========================
# Programa principal
# =========================

def main():
    print("=== Traductor de reuniones - subtítulo en español ===")
    print("Pulsa Ctrl + C para detener.\n")

    temp_wav = "temp_reunion.wav"

    try:
        while True:
            # 1) Grabar fragmento de audio
            record_audio(temp_wav)

            # 2) Subir a AssemblyAI y transcribir
            audio_url = upload_to_assemblyai(temp_wav)
            text_en = transcribe_with_assemblyai(audio_url)

            # 3) Traducir con DeepL
            text_es = translate_with_deepl(text_en)

            if not text_es.strip():
                # Si no hay texto útil, pasamos al siguiente fragmento
                continue

            # 4) Limpiar pantalla y mostrar solo el último subtítulo
            os.system("cls")  # en Windows; en Linux/Mac sería "clear"
            print("=== Traducción en tiempo casi real (ES) ===\n")
            print(text_es)

    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
    except Exception as e:
        print("\nOcurrió un error:", e)


if __name__ == "__main__":
    main()
