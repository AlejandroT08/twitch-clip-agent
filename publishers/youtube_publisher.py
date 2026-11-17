import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubeShortsPublisher:
    """
    Publicador oficial de YouTube Shorts usando YouTube Data API v3.
    """
    def __init__(self, client_secrets_file: str = "client_secret.json", token_pickle: str = "yt_token.pickle"):
        self.client_secrets_file = client_secrets_file
        self.token_pickle = token_pickle
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        creds = None
        if os.path.exists(self.token_pickle):
            with open(self.token_pickle, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"No se encontró el archivo '{self.client_secrets_file}'. "
                        "Descárgalo desde Google Cloud Console (Credenciales OAuth 2.0)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_pickle, "wb") as token:
                pickle.dump(creds, token)

        return build("youtube", "v3", credentials=creds)

    def upload_short(
        self,
        video_path: str,
        title: str,
        description: str = "",
        category_id: str = "20",
        privacy_status: str = "public"
    ) -> str:
        # Asegura la etiqueta #Shorts en el título para el feed de Shorts
        if "#Shorts" not in title and "#shorts" not in title:
            title = f"{title} #Shorts"

        body = {
            "snippet": {
                "title": title[:100],
                "description": f"{description}\n\n#Shorts #Twitch #Viral",
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube] Progreso de subida: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        print(f"[YouTube] ¡Publicado con éxito! URL: https://youtube.com/shorts/{video_id}")
        return video_id
