import os

class TikTokPublisher:
    """
    Publicador automático para TikTok utilizando `tiktok-uploader` con cookies de sesión.
    No requiere aprobación manual de cuenta de empresa en TikTok Developers.
    """
    def __init__(self, cookies_file: str = "tiktok_cookies.txt", headless: bool = True):
        self.cookies_file = cookies_file
        self.headless = headless

    def upload_video(self, video_path: str, caption: str) -> bool:
        if not os.path.exists(self.cookies_file):
            print(f"[TikTok] ADVERTENCIA: No se encontró '{self.cookies_file}'. Omitiendo subida a TikTok.")
            print("[TikTok] Para habilitar TikTok, exporta tus cookies con la extensión 'Get cookies.txt LOCALLY'.")
            return False

        try:
            from tiktok_uploader.upload import upload_video
            print(f"[TikTok] Subiendo video con caption: {caption[:40]}...")
            
            # upload_video retorna boolean o lista de videos subidos
            success = upload_video(
                filename=video_path,
                description=caption,
                cookies=self.cookies_file,
                headless=self.headless
            )
            print(f"[TikTok] Resultado de subida: {'Completado' if success else 'Fallido'}")
            return bool(success)
        except Exception as e:
            print(f"[TikTok] Error durante la subida a TikTok: {e}")
            return False
