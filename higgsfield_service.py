import os
import glob
import shutil
import asyncio
import requests
import subprocess
import higgsfield_client


def find_ffmpeg() -> str:
    """Encuentra ffmpeg en PATH o en la ruta de instalación de WinGet en Windows."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        matches = glob.glob(
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "ffmpeg.exe"),
            recursive=True,
        )
        if matches:
            ffmpeg_dir = os.path.dirname(matches[0])
            if ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
            return matches[0]
    return "ffmpeg"


class HiggsfieldService:
    """
    Puente hacia la API oficial de Higgsfield AI usando `higgsfield-client`.
    Soporta:
      - `bytedance/seedance-2.5/video-edit`: Edita/estiliza el clip real de Twitch con un prompt.
      - `bytedance/seedance-2.5/text-to-video`: Genera un video nuevo vertical 9:16 desde el prompt.
    Si Higgsfield devuelve `not_enough_credits` u otro error de saldo, aplica automáticamente
    edición local profesional en 9:16 con subtítulos en español quemados vía FFmpeg (0 coste).
    """
    def __init__(
        self,
        model: str = "bytedance/seedance-2.5/video-edit",
        max_input_seconds: int = 15,
        duration: int = 5,
        resolution: str = "720p",
        aspect_ratio: str = "9:16",
        generate_audio: bool = True,
        output_dir: str = "outputs"
    ):
        self.model = model
        self.max_input_seconds = min(max_input_seconds, 30)  # Límite Seedance video-edit = 30s
        self.duration = duration
        self.resolution = resolution
        self.aspect_ratio = aspect_ratio
        self.generate_audio = generate_audio
        self.output_dir = output_dir
        self.ffmpeg_bin = find_ffmpeg()
        self.last_mode_used = "higgsfield"
        os.makedirs(self.output_dir, exist_ok=True)

        if not os.getenv("HF_KEY"):
            print("[Higgsfield] ADVERTENCIA: Variable HF_KEY no detectada en .env ni .env.local")

    def process_clip(self, clip_id: str, local_video_path: str, prompt: str, srt_path: str = None) -> str:
        """
        1. Envía el clip a Higgsfield AI (Seedance 2.5).
        2. Si no hay saldo en la API de Higgsfield, genera automáticamente la versión
           vertical 9:16 con subtítulos sincronizados en español usando FFmpeg local.
        """
        print(f"[Higgsfield] Modelo: '{self.model}'")
        print(f"[Higgsfield] Prompt aplicado: {prompt}")

        final_output_path = os.path.join(self.output_dir, f"{clip_id}_final_9x16.mp4")

        try:
            if "text-to-video" in self.model:
                arguments = {
                    "prompt": prompt,
                    "duration": self.duration,
                    "resolution": self.resolution,
                    "aspect_ratio": self.aspect_ratio,
                    "output_format": "mp4",
                    "generate_audio": self.generate_audio,
                }
            else:
                trimmed_path = self._trim_input_video(clip_id, local_video_path, self.max_input_seconds)
                print(f"[Higgsfield] Subiendo clip fuente ({os.path.basename(trimmed_path)})...")
                uploaded_media_url = asyncio.run(
                    higgsfield_client.upload_file_async(trimmed_path)
                )
                print("[Higgsfield] Archivo subido. Esperando renderizado de Seedance 2.5...")
                arguments = {
                    "prompt": prompt,
                    "video_url": uploaded_media_url,
                }

            result = higgsfield_client.subscribe(
                self.model,
                arguments=arguments,
            )

            output_url = self._extract_video_url(result)
            if not output_url:
                raise RuntimeError(f"Higgsfield completó pero no devolvió URL de video: {result}")

            raw_output_path = os.path.join(self.output_dir, f"{clip_id}_higgsfield_raw.mp4")
            self._download_file(output_url, raw_output_path)

            self.last_mode_used = "higgsfield"
            self._ensure_vertical_format(raw_output_path, final_output_path, srt_path=None, blur_bg=False)
            return final_output_path

        except Exception as e:
            err_msg = str(e)
            if "not_enough_credits" in err_msg:
                print("\n[Higgsfield] ⚠️ Tu cuenta de API en open.higgsfield.ai no tiene saldo/créditos cargados ('not_enough_credits').")
                print("             Nota: El saldo de API de Higgsfield es independiente de la suscripción web.")
                print("             ➔ Activando respaldo local automático: FFmpeg 9:16 + subtítulos en español (coste $0)...")
            else:
                print(f"\n[Higgsfield] ⚠️ Error en API de Higgsfield ({err_msg}).")
                print("             ➔ Activando respaldo local automático: FFmpeg 9:16 + subtítulos en español...")

            self.last_mode_used = f"local_fallback ({err_msg})"
            self._ensure_vertical_format(local_video_path, final_output_path, srt_path=srt_path, blur_bg=True)
            return final_output_path

    def _trim_input_video(self, clip_id: str, input_path: str, max_seconds: int) -> str:
        """Recorta el clip fuente a max_seconds con FFmpeg para cumplir límites y ahorrar créditos."""
        trimmed_path = os.path.join(self.output_dir, f"{clip_id}_trimmed_{max_seconds}s.mp4")
        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", input_path,
            "-t", str(max_seconds),
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            trimmed_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return trimmed_path
        except Exception:
            return input_path

    def _extract_video_url(self, result: dict) -> str:
        if isinstance(result, dict):
            if "video" in result and isinstance(result["video"], dict):
                return result["video"].get("url", "")
            if "videos" in result and isinstance(result["videos"], list) and len(result["videos"]) > 0:
                item = result["videos"][0]
                return item.get("url", "") if isinstance(item, dict) else str(item)
            if "url" in result:
                return result["url"]
        return ""

    def _download_file(self, url: str, dest_path: str):
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def _escape_srt_for_ffmpeg(self, srt_path: str) -> str:
        """Escapa correctamente rutas de Windows para el filtro subtitles de FFmpeg."""
        abs_path = os.path.abspath(srt_path).replace("\\", "/")
        return abs_path.replace(":", "\\:")

    def _ensure_vertical_format(
        self,
        input_path: str,
        output_path: str,
        srt_path: str = None,
        blur_bg: bool = False
    ):
        """
        Usa FFmpeg local (0 tokens) para garantizar resolución 1080x1920 (9:16),
        códec H.264, audio AAC y opcionalmente quemar subtítulos en español estilo TikTok.
        """
        has_srt = bool(srt_path and os.path.exists(srt_path))
        subtitle_style = (
            "FontName=Arial,FontSize=16,Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=55"
        )

        if blur_bg:
            # Formato TikTok/Shorts profesional para clips 16:9: fondo difuminado 9:16 + clip nítido centrado
            base_filter = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,boxblur=20:5[bg];"
                "[0:v]scale=1080:-2[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[vbase]"
            )
            if has_srt:
                escaped = self._escape_srt_for_ffmpeg(srt_path)
                filter_complex = f"{base_filter};[vbase]subtitles='{escaped}':force_style='{subtitle_style}'[vout]"
            else:
                filter_complex = f"{base_filter};[vbase]null[vout]"

            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", input_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            if has_srt:
                escaped = self._escape_srt_for_ffmpeg(srt_path)
                vf = f"{vf},subtitles='{escaped}':force_style='{subtitle_style}'"

            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", input_path,
                "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except FileNotFoundError:
            print("[FFmpeg] ADVERTENCIA: FFmpeg no está instalado en el PATH. Usando video sin re-escalar.")
            shutil.copy2(input_path, output_path)
        except subprocess.CalledProcessError as e:
            err_text = e.stderr.decode("utf-8", errors="ignore")[-300:]
            print(f"[FFmpeg] Advertencia con filtro avanzado ({err_text}). Reintentando conversión simple 9:16...")
            simple_cmd = [
                self.ffmpeg_bin, "-y",
                "-i", input_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
            subprocess.run(simple_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
