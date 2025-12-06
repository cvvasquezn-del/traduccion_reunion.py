import os
import queue

import requests
import sounddevice as sd
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
from dotenv import load_dotenv

# =========================
# Configuración
# =========================

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

if not ASSEMBLYAI_API_KEY or not DEEPL_API_KEY:
    raise RuntimeError("Faltan ASSEMBLYAI_API_KEY o DEEPL_API_KEY en .env")

# Para otras partes del SDK; no es estrictamente necesario, pero no molesta
aai.settings.api_key = ASSEMBLYAI_API_KEY

SAMPLE_RATE = 16000  # Hz, mono


# =========================
# Captura de audio (sounddevice, sin PyAudio)
# =========================

def microphone_stream(sample_rate: int):
    """
    Generador que entrega audio PCM16 mono en tiempo real usando sounddevice.
    Usa el dispositivo de grabación por defecto (Mezcla estéreo).
    Envía bloques de ~100 ms (AssemblyAI exige 50–1000 ms por chunk).
    """
    q = queue.Queue()

    # 100 ms de audio -> frames = sample_rate * 0.1
    block_frames = int(sample_rate * 0.1)  # 1600 frames a 16 kHz

    def callback(indata, frames, time_info, status):
        if status:
            # Si quieres depurar, puedes hacer: print(status)
            pass
        q.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=block_frames,  # tamaño de bloque fijo ~100 ms
        callback=callback,
    ):
        while True:
            data = q.get()
            yield data



# =========================
# Traducción con DeepL
# =========================

def translate_to_spanish(text_en: str) -> str:
    """Traduce texto EN -> ES usando DeepL API Free."""
    text_en = text_en.strip()
    if not text_en:
        return ""

    url = "https://api-free.deepl.com/v2/translate"
    data = {
        "auth_key": DEEPL_API_KEY,
        "text": text_en,
        "source_lang": "EN",
        "target_lang": "ES",
    }

    resp = requests.post(url, data=data)
    resp.raise_for_status()
    data_json = resp.json()
    translations = data_json.get("translations", [])
    if not translations:
        return ""
    return translations[0]["text"]


# =========================
# Callbacks de streaming
# =========================

def on_begin(client: StreamingClient, event: BeginEvent) -> None:
    os.system("cls")
    print("=== Sesión de streaming iniciada ===")
    print("Deja sonar la reunión en inglés (Mezcla estéreo).")
    print("Pulsa Ctrl + C para detener.\n")


def on_turn(client: StreamingClient, event: TurnEvent) -> None:
    """
    Se llama cuando AssemblyAI detecta un 'turno' de habla.
    Usamos sólo los turnos completos y ya formateados.
    """
    transcript = (event.transcript or "").strip()
    if not transcript:
        return

    if event.end_of_turn and event.turn_is_formatted:
        try:
            text_es = translate_to_spanish(transcript)
        except Exception as e:
            os.system("cls")
            print("Error traduciendo con DeepL:", e)
            print("\n(Último texto EN):")
            print(transcript)
            return

        text_es = text_es.strip()
        if not text_es:
            return

        os.system("cls")
        print("=== Traducción en tiempo (casi) real (ES) ===\n")
        print(text_es)


def on_terminated(client: StreamingClient, event: TerminationEvent) -> None:
    print(
        f"\nSesión terminada. Audio procesado: "
        f"{event.audio_duration_seconds:.1f} segundos"
    )


def on_error(client: StreamingClient, error: StreamingError) -> None:
    print("\n[ERROR en streaming]:", error)


# =========================
# Programa principal
# =========================

def main() -> None:
    # Crear cliente de streaming
    client = StreamingClient(
        StreamingClientOptions(
            api_key=ASSEMBLYAI_API_KEY,
            api_host="streaming.assemblyai.com",
        )
    )

    # Registrar callbacks
    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    # Configuración de la sesión: sólo StreamingParameters
    params = StreamingParameters(
        sample_rate=SAMPLE_RATE,
        format_turns=True,  # frases ya formateadas
    )

    try:
        # Conectar al servicio de streaming
        client.connect(params)

        # Generador de audio con sounddevice (usa Mezcla estéreo)
        audio_gen = microphone_stream(SAMPLE_RATE)

        # Empieza a enviar audio y recibir transcripciones
        client.stream(audio_gen)

    except KeyboardInterrupt:
        print("\nDetenido por el usuario (Ctrl + C).")
    finally:
        client.disconnect(terminate=True)


if __name__ == "__main__":
    main()
