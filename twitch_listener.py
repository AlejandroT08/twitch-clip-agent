import os
import requests
import datetime
import yt_dlp
from typing import List, Dict, Optional

class TwitchActiveListener:
    def __init__(self, client_id: str, client_secret: str, download_dir: str = "downloads"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.access_token = self._authenticate()
        self.broadcaster_cache: Dict[str, str] = {}

    def _authenticate(self) -> str:
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        res = requests.post(url, data=params, timeout=15)
        res.raise_for_status()
        return res.json()["access_token"]

    def _headers(self) -> Dict[str, str]:
        return {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }

    def get_broadcaster_id(self, channel_login: str) -> Optional[str]:
        # Permite tanto "rubius" como "https://www.twitch.tv/rubius"
        channel_login = channel_login.strip().rstrip("/").split("/")[-1].lower()
        if channel_login in self.broadcaster_cache:
            return self.broadcaster_cache[channel_login]

        url = f"https://api.twitch.tv/helix/users?login={channel_login}"
        res = requests.get(url, headers=self._headers(), timeout=15)
        if res.status_code == 401:
            self.access_token = self._authenticate()
            res = requests.get(url, headers=self._headers(), timeout=15)
        res.raise_for_status()
        data = res.json().get("data", [])
        if data:
            bid = data[0]["id"]
            self.broadcaster_cache[channel_login] = bid
            return bid
        return None

    def is_channel_live(self, broadcaster_id: str) -> bool:
        """Verifica si el streamer está transmitiendo en directo actualmente."""
        url = f"https://api.twitch.tv/helix/streams?user_id={broadcaster_id}"
        res = requests.get(url, headers=self._headers(), timeout=15)
        if res.status_code == 401:
            self.access_token = self._authenticate()
            res = requests.get(url, headers=self._headers(), timeout=15)
        res.raise_for_status()
        return len(res.json().get("data", [])) > 0

    def fetch_recent_clips(
        self,
        broadcaster_id: str,
        lookback_seconds: int = 120,
        min_duration: float = 10.0,
        max_duration: float = 60.0
    ) -> List[Dict]:
        """
        Escucha Activa: Obtiene clips recién creados por la comunidad o mods
        en los últimos `lookback_seconds` segundos.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        started_at = (now_utc - datetime.timedelta(seconds=lookback_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = (
            f"https://api.twitch.tv/helix/clips"
            f"?broadcaster_id={broadcaster_id}"
            f"&started_at={started_at}"
            f"&first=20"
        )
        res = requests.get(url, headers=self._headers(), timeout=15)
        if res.status_code == 401:
            self.access_token = self._authenticate()
            res = requests.get(url, headers=self._headers(), timeout=15)
        res.raise_for_status()

        raw_clips = res.json().get("data", [])
        filtered_clips = []
        for clip in raw_clips:
            duration = float(clip.get("duration", 0))
            if min_duration <= duration <= max_duration:
                filtered_clips.append(clip)

        # Ordenar por más reciente primero
        filtered_clips.sort(key=lambda c: c.get("created_at", ""), reverse=True)
        return filtered_clips

    def download_clip(self, clip_id: str, clip_url: str, retries: int = 2) -> str:
        """Descarga el archivo MP4 del clip de Twitch usando yt-dlp (0 tokens) con reintento ante propagación CDN."""
        import time

        output_path = os.path.join(self.download_dir, f"{clip_id}.mp4")
        if os.path.exists(output_path):
            return output_path

        ydl_opts = {
            "outtmpl": output_path,
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True
        }

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([clip_url])
                return output_path
            except Exception as e:
                last_err = e
                if attempt < retries:
                    print(f"      [Twitch CDN] Clip recién creado aún propagándose, reintentando en 5s ({attempt}/{retries})...")
                    time.sleep(5)
        raise last_err
