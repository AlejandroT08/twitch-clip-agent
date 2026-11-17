import os
import sys
import time
import yaml
from dotenv import load_dotenv

# Cargar variables de entorno de .env y .env.local (si existe)
load_dotenv(".env")
load_dotenv(".env.local", override=True)

from database import DatabaseManager
from twitch_listener import TwitchActiveListener
from transcriber import LocalTranscriber
from optimizer import TokenOptimizerAgent
from higgsfield_service import HiggsfieldService
from publishers.youtube_publisher import YouTubeShortsPublisher
from publishers.tiktok_publisher import TikTokPublisher

def load_config(config_path: str = "config.yaml") -> dict:
    if not os.path.exists(config_path):
        print(f"Error: No se encontró el archivo de configuración '{config_path}'.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def print_banner():
    banner = """
    ===============================================================
       🤖 AGENTE DE ESCUCHA ACTIVA: TWITCH ➔ HIGGSFIELD ➔ REDES
       Optimización Extrema de Tokens | Detección en Tiempo Real
    ===============================================================
    """
    print(banner)

def main():
    print_banner()
    config = load_config()

    # Validar credenciales mínimas de Twitch
    twitch_id = os.getenv("TWITCH_CLIENT_ID")
    twitch_secret = os.getenv("TWITCH_CLIENT_SECRET")
    if not twitch_id or not twitch_secret or "tu_" in twitch_id:
        print("[!] ERROR CRÍTICO: Debes configurar TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en el archivo .env")
        print("Revisa el archivo README.md para ver los pasos a seguir.")
        sys.exit(1)

    # 1. Inicializar Base de Datos y Memoria
    db = DatabaseManager()
    print("[1/5] Base de datos SQLite lista (clips_history.db).")

    # 2. Inicializar Escucha Activa de Twitch
    twitch_listener = TwitchActiveListener(client_id=twitch_id, client_secret=twitch_secret)
    print(f"[2/5] Escucha de Twitch conectada. Canales: {config['twitch']['monitored_channels']}")

    # 3. Inicializar Transcriptor Local (0 Tokens)
    transcriber = LocalTranscriber(
        model_size=config["transcription"].get("model_size", "base"),
        device=config["transcription"].get("device", "cpu")
    )
    print("[3/5] Transcriptor local Whisper iniciado (Consumo: 0 tokens).")

    # 4. Inicializar Agente Optimizador de Tokens
    optimizer = TokenOptimizerAgent(
        provider=config["token_economy"].get("provider", "gemini"),
        model_name=config["token_economy"].get("model_name", "gemini-3.8-flash"),
        base_style=config["higgsfield"].get("base_style", "")
    )
    print(f"[4/5] Agente LLM configurado con '{config['token_economy']['model_name']}' (Llamada única consolidada).")

    # 5. Inicializar Higgsfield y Publicadores
    hf_cfg = config["higgsfield"]
    higgsfield = HiggsfieldService(
        model=hf_cfg.get("model", "bytedance/seedance-2.5/video-edit"),
        max_input_seconds=hf_cfg.get("max_input_seconds", 15),
        duration=hf_cfg.get("duration", 5),
        resolution=hf_cfg.get("resolution", "720p"),
        aspect_ratio=hf_cfg.get("aspect_ratio", "9:16"),
        generate_audio=hf_cfg.get("generate_audio", True),
    )
    
    yt_publisher = None
    if config["publishing"]["youtube"].get("enabled", False):
        try:
            secrets_file = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secret.json")
            if os.path.exists(secrets_file):
                yt_publisher = YouTubeShortsPublisher(client_secrets_file=secrets_file)
                print("[5/5] YouTube Shorts Publisher: Activo.")
            else:
                print(f"[5/5] YouTube Shorts Publisher: Omitido (no existe '{secrets_file}').")
        except Exception as e:
            print(f"[5/5] Error al iniciar YouTube Publisher: {e}")

    tiktok_publisher = None
    if config["publishing"]["tiktok"].get("enabled", False):
        cookies_file = os.getenv("TIKTOK_COOKIES_FILE", "tiktok_cookies.txt")
        tiktok_publisher = TikTokPublisher(
            cookies_file=cookies_file,
            headless=config["publishing"]["tiktok"].get("headless_browser", True)
        )
        print("[5/5] TikTok Publisher: Activo.")

    channels = config["twitch"]["monitored_channels"]
    poll_interval = config["twitch"].get("poll_interval_seconds", 30)
    only_live = config["twitch"].get("only_when_live", True)
    lookback = config["twitch"].get("lookback_seconds", 120)

    print(f"\n🚀 Agente en ejecución. Escuchando canales cada {poll_interval} segundos...\n")

    try:
        while True:
            for channel in channels:
                broadcaster_id = twitch_listener.get_broadcaster_id(channel)
                if not broadcaster_id:
                    print(f"[-] Canal no encontrado: {channel}")
                    continue

                # Verificar si está en directo (si la opción está habilitada)
                if only_live:
                    if not twitch_listener.is_channel_live(broadcaster_id):
                        # Streamer offline, no procesar para ahorrar recursos
                        continue

                # Escucha activa: buscar clips recién creados en los últimos X segundos
                recent_clips = twitch_listener.fetch_recent_clips(
                    broadcaster_id=broadcaster_id,
                    lookback_seconds=lookback,
                    min_duration=config["twitch"].get("min_duration_seconds", 10),
                    max_duration=config["twitch"].get("max_duration_seconds", 60)
                )

                for clip in recent_clips:
                    clip_id = clip["id"]
                    if db.is_clip_processed(clip_id):
                        continue

                    title = clip.get("title", "Momento Twitch")
                    clip_url = clip.get("url")
                    created_at = clip.get("created_at")

                    print(f"\n🎯 [NUEVO CLIP DETECTADO] Streamer: {channel} | ID: {clip_id}")
                    print(f"   Título: {title} | Creado: {created_at}")

                    # Registrar inicio para evitar procesamientos duplicados
                    db.record_clip_started(clip_id, channel, title, clip_url, created_at)

                    # Paso 1: Descargar clip con yt-dlp (0 tokens)
                    print("   [Paso 1/5] Descargando clip...")
                    try:
                        local_clip_path = twitch_listener.download_clip(clip_id, clip_url)
                    except Exception as e:
                        print(f"   [!] Clip no disponible en CDN de Twitch ({e}). Omitiendo...")
                        continue

                    # Paso 2: Transcribir con faster-whisper local (0 tokens) + generar .srt
                    print("   [Paso 2/5] Transcribiendo audio en local...")
                    max_chars = config["token_economy"].get("max_transcript_chars", 500)
                    srt_file = os.path.join("outputs", f"{clip_id}.srt")
                    transcript, srt_path = transcriber.transcribe_with_srt(
                        local_clip_path,
                        srt_output_path=srt_file,
                        max_chars=max_chars
                    )
                    if transcript:
                        print(f"   Transcripción: \"{transcript[:70]}...\"")

                    # Paso 3: LLM Ultraligero - Generar Prompt Higgsfield + Copys (1 llamada)
                    print("   [Paso 3/5] Generando prompt y metadatos con LLM (Llamada única consolidada)...")
                    try:
                        creative_pkg, prompt_tokens, comp_tokens = optimizer.generate_package(
                            streamer_name=channel,
                            clip_title=title,
                            transcript=transcript
                        )
                        print(f"   Prompt Higgsfield: {creative_pkg.higgsfield_prompt[:80]}...")
                        print(f"   Tokens consumidos: Entrada={prompt_tokens}, Salida={comp_tokens} (Total: {prompt_tokens + comp_tokens})")
                    except Exception as e:
                        print(f"   [!] Error en el optimizador LLM: {e}")
                        continue

                    # Paso 4: Generación / Estilización con Higgsfield AI (o respaldo local 9:16 + subtítulos)
                    print("   [Paso 4/5] Enviando a Higgsfield AI...")
                    try:
                        final_video_path = higgsfield.process_clip(
                            clip_id=clip_id,
                            local_video_path=local_clip_path,
                            prompt=creative_pkg.higgsfield_prompt,
                            srt_path=srt_path
                        )
                        print(f"   Video generado listo en: {final_video_path} (Modo: {higgsfield.last_mode_used})")
                    except Exception as e:
                        print(f"   [!] Error en Higgsfield AI: {e}")
                        final_video_path = local_clip_path # Fallback: usar el clip original si Higgsfield falla

                    # Paso 5: Publicación Automática
                    yt_id = None
                    if yt_publisher:
                        print("   [Paso 5/5 A] Publicando en YouTube Shorts...")
                        try:
                            yt_id = yt_publisher.upload_short(
                                video_path=final_video_path,
                                title=creative_pkg.youtube_title,
                                description=f"Clip de {channel}: {title}",
                                category_id=config["publishing"]["youtube"].get("category_id", "20"),
                                privacy_status=config["publishing"]["youtube"].get("privacy_status", "public")
                            )
                        except Exception as e:
                            print(f"   [!] Error subiendo a YouTube: {e}")

                    tiktok_ok = False
                    if tiktok_publisher:
                        print("   [Paso 5/5 B] Publicando en TikTok...")
                        tiktok_ok = tiktok_publisher.upload_video(
                            video_path=final_video_path,
                            caption=creative_pkg.tiktok_caption
                        )

                    # Guardar resultados finales y tokens en SQLite
                    db.update_clip_success(
                        clip_id=clip_id,
                        higgsfield_url=final_video_path,
                        youtube_video_id=yt_id,
                        tiktok_status="published" if tiktok_ok else "skipped_or_failed",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=comp_tokens
                    )

                    # Mostrar resumen de ahorro de tokens acumulado
                    metrics = db.get_metrics_summary()
                    print("\n📊 [REPORTE ACUMULADO DEL AGENTE]")
                    print(f"   • Clips procesados: {metrics['total_clips_processed']}")
                    print(f"   • Tokens totales gastados: {metrics['total_tokens_used']}")
                    print(f"   • Coste estimado total: ${metrics['estimated_cost_usd']} USD\n")

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n[Detención] Agente detenido correctamente por el usuario.")
        metrics = db.get_metrics_summary()
        print(f"Resumen final: {metrics['total_clips_processed']} clips procesados, {metrics['total_tokens_used']} tokens gastados.")

if __name__ == "__main__":
    main()
