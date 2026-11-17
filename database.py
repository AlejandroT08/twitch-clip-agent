import sqlite3
import datetime
from typing import Optional, Dict

class DatabaseManager:
    def __init__(self, db_path: str = "clips_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_clips (
                    clip_id TEXT PRIMARY KEY,
                    broadcaster_name TEXT,
                    title TEXT,
                    clip_url TEXT,
                    created_at TEXT,
                    processed_at TEXT,
                    higgsfield_url TEXT,
                    youtube_video_id TEXT,
                    tiktok_status TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def is_clip_processed(self, clip_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_clips WHERE clip_id = ?", (clip_id,))
            return cursor.fetchone() is not None

    def record_clip_started(self, clip_id: str, broadcaster_name: str, title: str, clip_url: str, created_at: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO processed_clips (
                    clip_id, broadcaster_name, title, clip_url, created_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (clip_id, broadcaster_name, title, clip_url, created_at, datetime.datetime.utcnow().isoformat()))
            conn.commit()

    def update_clip_success(
        self,
        clip_id: str,
        higgsfield_url: str,
        youtube_video_id: Optional[str] = None,
        tiktok_status: str = "success",
        prompt_tokens: int = 0,
        completion_tokens: int = 0
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE processed_clips
                SET higgsfield_url = ?,
                    youtube_video_id = ?,
                    tiktok_status = ?,
                    prompt_tokens = ?,
                    completion_tokens = ?,
                    total_tokens = ?
                WHERE clip_id = ?
            """, (
                higgsfield_url,
                youtube_video_id,
                tiktok_status,
                prompt_tokens,
                completion_tokens,
                prompt_tokens + completion_tokens,
                clip_id
            ))
            conn.commit()

    def get_metrics_summary(self) -> Dict[str, float]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*),
                    SUM(total_tokens),
                    SUM(prompt_tokens),
                    SUM(completion_tokens)
                FROM processed_clips
            """)
            row = cursor.fetchone()
            total_clips = row[0] or 0
            total_tokens = row[1] or 0
            prompt_tokens = row[2] or 0
            comp_tokens = row[3] or 0

            # Estimación económica con Gemini Flash / GPT-4o-mini (~$0.10 por 1M tokens)
            estimated_cost_usd = (total_tokens / 1_000_000.0) * 0.15

            return {
                "total_clips_processed": total_clips,
                "total_tokens_used": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": comp_tokens,
                "estimated_cost_usd": round(estimated_cost_usd, 5)
            }
