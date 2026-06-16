import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    slug           TEXT NOT NULL UNIQUE,
    title          TEXT,
    score          INTEGER,
    status         TEXT,
    used_kling     INTEGER DEFAULT 0,
    created_at     TEXT,
    output_path    TEXT,
    thumbnail_path TEXT,
    amazon_link    TEXT,
    shopee_link    TEXT,
    youtube_id     TEXT,
    youtube_url    TEXT,
    views          INTEGER DEFAULT 0,
    updated_at     TEXT
)
"""


class JobTracker:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def upsert(self, slug, **fields):
        """Insere ou atualiza um job pelo slug."""
        fields["updated_at"] = datetime.now().isoformat()
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id FROM jobs WHERE slug = ?", (slug,)
            ).fetchone()

            if exists:
                set_clause = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(
                    f"UPDATE jobs SET {set_clause} WHERE slug = ?",
                    [*fields.values(), slug],
                )
            else:
                fields["slug"] = slug
                cols   = ", ".join(fields.keys())
                params = ", ".join("?" for _ in fields)
                conn.execute(
                    f"INSERT INTO jobs ({cols}) VALUES ({params})",
                    list(fields.values()),
                )
            conn.commit()

    def print_summary(self):
        """Imprime resumo dos últimos 20 jobs no log."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT title, score, status, youtube_url, created_at
                FROM jobs ORDER BY created_at DESC LIMIT 20
            """).fetchall()

        if not rows:
            logger.info("Nenhum job registrado ainda.")
            return

        logger.info("=== Histórico (últimos 20 jobs) ===")
        for title, score, status, yt_url, created in rows:
            yt   = yt_url or "sem upload"
            date = (created or "")[:10]
            logger.info(f"  [{status}] {title} (score:{score}) | {yt} | {date}")
