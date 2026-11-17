import os
import sys
import yaml
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)

from twitch_listener import TwitchActiveListener
from transcriber import LocalTranscriber
from optimizer import TokenOptimizerAgent
from higgsfield_service import HiggsfieldService


def main():
    print("===============================================================")
    print("  🧪 PRUEBA CONTROLADA DE 1 SOLO CLIP (SIN PUBLICAR EN REDES)")
    print("===============================================================\n")

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    channels = config["twitch"]["monitored_channels"]
    if not channels:
        print("[!] No hay canales configurados en config.yaml (twitch.monitored_channels).")
        sys.exit(1)

    channel = channels[0]
    print(f"[1/5] Canal objetivo desde config.yaml: '{channel}'")

    listener = TwitchActiveListener(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET"),
    )

    broadcaster_id = listener.get_broadcaster_id(channel)
    if not broadcaster_id:
        print(f"[!] No se encontró el canal '{channel}' en Twitch.")
        sys.exit(1)

    is_live = listener.is_channel_live(broadcaster_id)
    print(f"      Broadcaster ID: {broadcaster_id} | Estado: {'EN VIVO 🔴' if is_live else 'Offline ⚫'}")

    # Buscar el clip más reciente ampliando ventana solo si no hubo uno en los últimos 10 min
    clips = []
    for window_sec, label in [(600, "últimos 10 min"), (3600, "última hora"), (86400, "últimas 24 h")]:
        clips = listener.fetch_recent_clips(
            broadcaster_id=broadcaster_id,
            lookback_seconds=window_sec,
            min_duration=config["twitch"].get("min_duration_seconds", 10),
            max_duration=config["twitch"].get("max_duration_seconds", 60),
        )
        if clips:
            print(f"      Encontrados {len(clips)} clip(s) en {label}. Tomando el más reciente.")
            break

    if not clips:
        print("[!] No se encontraron clips recientes en las últimas 24 horas para este canal.")
        sys.exit(1)

    # Paso 2: Intentar descargar el primer clip disponible en CDN (por si el más nuevo fue borrado o está codificando)
    clip = None
    local_clip_path = None
    print("\n[2/5] Descargando clip original con yt-dlp (0 tokens)...")
    for candidate in clips:
        cid = candidate["id"]
        ctitle = candidate.get("title", "Momento Twitch")
        curl = candidate["url"]
        cdur = candidate.get("duration", 0)
        print(f"\n🎯 Probando clip: {cid} | Título: {ctitle} | Duración: {cdur}s")
        try:
            local_clip_path = listener.download_clip(cid, curl)
            clip = candidate
            break
        except Exception as e:
            print(f"      [!] Clip no disponible en CDN ({e}). Probando el siguiente...")

    if not clip or not local_clip_path:
        print("[!] Ninguno de los clips encontrados pudo descargarse de Twitch CDN.")
        sys.exit(1)

    clip_id = clip["id"]
    clip_title = clip.get("title", "Momento Twitch")
    clip_url = clip["url"]
    print(f"      Guardado en: {os.path.abspath(local_clip_path)}")

    # Paso 3: Transcripción local con faster-whisper (0 tokens) + generación de subtítulos .srt
    print("\n[3/5] Transcribiendo audio localmente con faster-whisper (0 tokens)...")
    transcriber = LocalTranscriber(
        model_size=config["transcription"].get("model_size", "base"),
        device=config["transcription"].get("device", "cpu"),
    )
    srt_file = os.path.join("outputs", f"{clip_id}.srt")
    transcript, srt_path = transcriber.transcribe_with_srt(
        local_clip_path,
        srt_output_path=srt_file,
        max_chars=config["token_economy"].get("max_transcript_chars", 500),
    )
    print(f"      Transcripción: \"{transcript or '(sin voz detectada)'}\"")
    if srt_path:
        print(f"      Subtítulos .srt guardados en: {os.path.abspath(srt_path)}")

    # Paso 4: 1 sola llamada a Gemini Flash
    print("\n[4/5] Generando prompt para Higgsfield + copys con LLM (1 llamada consolidada)...")
    optimizer = TokenOptimizerAgent(
        provider=config["token_economy"].get("provider", "gemini"),
        model_name=config["token_economy"].get("model_name", "gemini-3.8-flash"),
        base_style=config["higgsfield"].get("base_style", ""),
    )
    pkg, p_tok, c_tok = optimizer.generate_package(
        streamer_name=channel,
        clip_title=clip_title,
        transcript=transcript,
    )
    total_tok = p_tok + c_tok
    est_usd = (total_tok / 1_000_000.0) * 0.15

    print("\n✨ Paquete generado por el Agente:")
    print(f"   • Prompt Higgsfield: {pkg.higgsfield_prompt}")
    print(f"   • Título YouTube:    {pkg.youtube_title}")
    print(f"   • Caption TikTok:    {pkg.tiktok_caption}")
    print(f"   • Tokens usados:     Entrada={p_tok} | Salida={c_tok} | Total={total_tok} (~${est_usd:.6f} USD)")

    # Confirmación interactiva antes de consumir saldo de Higgsfield (omitir con --yes / -y)
    print("\n[5/5] Paso final: Envío a Higgsfield AI")
    hf_cfg = config["higgsfield"]
    print(f"      Modelo configurado: {hf_cfg.get('model')}")
    print(f"      Recorte máximo:     {hf_cfg.get('max_input_seconds', 15)} segundos")
    auto_yes = any(arg in ("--yes", "-y") for arg in sys.argv[1:])
    if not auto_yes:
        confirm = input("\n¿Enviar este clip ahora a Higgsfield AI (consume saldo de tu cuenta)? [S/n]: ").strip().lower()
        if confirm in ("n", "no"):
            print("\nPrueba detenida antes de Higgsfield. El clip original quedó en:", os.path.abspath(local_clip_path))
            return
    else:
        print("      Modo automático (--yes): enviando directamente a Higgsfield AI...")

    higgsfield = HiggsfieldService(
        model=hf_cfg.get("model", "bytedance/seedance-2.5/video-edit"),
        max_input_seconds=hf_cfg.get("max_input_seconds", 15),
        duration=hf_cfg.get("duration", 5),
        resolution=hf_cfg.get("resolution", "720p"),
        aspect_ratio=hf_cfg.get("aspect_ratio", "9:16"),
        generate_audio=hf_cfg.get("generate_audio", True),
    )

    final_video = higgsfield.process_clip(
        clip_id=clip_id,
        local_video_path=local_clip_path,
        prompt=pkg.higgsfield_prompt,
        srt_path=srt_path,
    )

    print("\n===============================================================")
    print("  ✅ PRUEBA DE 1 CLIP COMPLETADA CON ÉXITO")
    print(f"  ⚙️  Modo usado: {higgsfield.last_mode_used}")
    print(f"  🎬 Video final 9:16 listo en:\n     {os.path.abspath(final_video)}")
    print("  (No se subió a YouTube ni TikTok en esta prueba)")
    print("===============================================================")


if __name__ == "__main__":
    main()
