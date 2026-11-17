import os
from typing import Tuple, Optional

# Evitar advertencias innecesarias de symlinks de HuggingFace en Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


def _format_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    secs = ms // 1000
    ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


class LocalTranscriber:
    """
    Transcribe el audio del clip localmente usando faster-whisper (si está instalado).
    Consumo de API externa / tokens de IA: 0.
    También genera archivos .srt sincronizados en español para subtítulos limpios con FFmpeg.
    """
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model = None
        if WHISPER_AVAILABLE:
            try:
                print(f"[Transcriber] Cargando modelo local Whisper ({model_size} en {device})...")
                compute_type = "int8" if device == "cpu" else "float16"
                self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            except Exception as e:
                print(f"[Transcriber] Advertencia al iniciar Whisper: {e}. Continuando en modo ligero.")
        else:
            print("[Transcriber] Modo ligero activo (faster-whisper no instalado). Se usarán el título y metadatos del clip.")

    def transcribe(self, video_path: str, max_chars: int = 500) -> str:
        text, _ = self.transcribe_with_srt(video_path, srt_output_path=None, max_chars=max_chars)
        return text

    def transcribe_with_srt(
        self,
        video_path: str,
        srt_output_path: Optional[str] = None,
        max_chars: int = 500
    ) -> Tuple[str, Optional[str]]:
        if not self.model or not os.path.exists(video_path):
            return "", None

        try:
            segments_iter, _ = self.model.transcribe(video_path, beam_size=3, vad_filter=True)
            segments = list(segments_iter)
            full_text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

            generated_srt = None
            if srt_output_path and segments:
                os.makedirs(os.path.dirname(os.path.abspath(srt_output_path)), exist_ok=True)
                with open(srt_output_path, "w", encoding="utf-8") as f:
                    idx = 1
                    for seg in segments:
                        text = seg.text.strip()
                        if not text:
                            continue
                        start_ts = _format_srt_timestamp(seg.start)
                        end_ts = _format_srt_timestamp(seg.end)
                        f.write(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n\n")
                        idx += 1
                generated_srt = srt_output_path

            return full_text[:max_chars].strip(), generated_srt
        except Exception as e:
            print(f"[Transcriber] Advertencia: No se pudo transcribir ({e}). Se usará el título del clip.")
            return "", None
