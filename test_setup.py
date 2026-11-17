import os
import shutil
import yaml
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)

def run_diagnostics():
    print("==============================================")
    print("  🔍 DIAGNÓSTICO DEL ENTORNO Y CREDENCIALES")
    print("==============================================\n")

    # 1. Librerías
    libs = [
        ("requests", "requests"),
        ("yt-dlp", "yt_dlp"),
        ("faster-whisper", "faster_whisper"),
        ("google-genai", "google.genai"),
        ("higgsfield-client", "higgsfield_client"),
        ("tiktok-uploader", "tiktok_uploader"),
        ("google-api-python-client", "googleapiclient"),
    ]
    print("1. Librerías de Python:")
    for label, mod in libs:
        try:
            __import__(mod)
            print(f"   [OK] {label}")
        except ImportError as e:
            print(f"   [X]  {label} -> Falta instalar ({e})")

    # 2. FFmpeg
    print("\n2. Herramientas del sistema:")
    from higgsfield_service import find_ffmpeg
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
        print(f"   [OK] FFmpeg encontrado en: {ffmpeg_path}")
    else:
        print("   [!]  FFmpeg NO encontrado en PATH (instala con: winget install -e --id Gyan.FFmpeg)")

    # 3. Credenciales en .env
    print("\n3. Credenciales en .env:")
    env_keys = [
        ("TWITCH_CLIENT_ID", True),
        ("TWITCH_CLIENT_SECRET", True),
        ("HF_KEY", True),
        ("GEMINI_API_KEY", False),
        ("OPENAI_API_KEY", False),
    ]
    for key, required in env_keys:
        val = os.getenv(key, "").strip()
        if val and "tu_" not in val:
            print(f"   [OK] {key} configurada")
        else:
            tag = "[FALTA - Obligatoria]" if required else "[Opcional / No configurada]"
            print(f"   {tag} {key}")

    # 4. Archivos de redes sociales
    print("\n4. Credenciales de Redes Sociales:")
    yt_file = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secret.json")
    tt_file = os.getenv("TIKTOK_COOKIES_FILE", "tiktok_cookies.txt")
    print(f"   {'[OK]' if os.path.exists(yt_file) else '[Opcional / Pendiente]'} YouTube: {yt_file}")
    print(f"   {'[OK]' if os.path.exists(tt_file) else '[Opcional / Pendiente]'} TikTok:  {tt_file}")

    # 5. Prueba real de conexión a Twitch
    tw_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
    tw_sec = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
    if tw_id and tw_sec and "tu_" not in tw_id:
        print("\n5. Prueba de conexión en vivo con Twitch:")
        try:
            from twitch_listener import TwitchActiveListener
            listener = TwitchActiveListener(tw_id, tw_sec)
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            for ch in cfg["twitch"]["monitored_channels"]:
                bid = listener.get_broadcaster_id(ch)
                if bid:
                    live = listener.is_channel_live(bid)
                    estado = "EN VIVO 🔴" if live else "Offline ⚫"
                    print(f"   [OK] Canal '{ch}' (ID: {bid}) -> {estado}")
                else:
                    print(f"   [!]  Canal '{ch}' no encontrado en Twitch")
        except Exception as e:
            print(f"   [X]  Error conectando a Twitch: {e}")

    print("\n==============================================")
    print("  Diagnóstico finalizado.")
    print("==============================================")

if __name__ == "__main__":
    run_diagnostics()
