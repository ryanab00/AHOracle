"""Database engine + view bootstrap."""
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()


def default_db_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("AHORACLE_DB_URL")
        or "sqlite:///ahoracle.db"
    )


def _normalize_url(url: str) -> str:
    """Ensure Postgres URLs use the psycopg (v3) driver and drop
    parameters the driver doesn't handle."""
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    if "channel_binding" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("channel_binding", None)
        url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    return url


def make_engine(db_url: str | None = None) -> Engine:
    url = _normalize_url(db_url or default_db_url())

    if url.startswith("postgresql"):
        return create_engine(
            url,
            pool_pre_ping=True,      # ping before checkout — Neon pooler drops idle conns
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,        # recycle every 5 min, well under pooler timeout
        )

    # Local SQLite fallback
    return create_engine(url)


# ─── Views ───────────────────────────────────────────────────────────────
# Identical structure; `(ts / 86400) * 86400` is integer math and works
# on both SQLite and Postgres without needing strftime/TO_CHAR.

_VIEWS_SQLITE = [
    """
    CREATE VIEW IF NOT EXISTS v_volume_at_price AS
    SELECT
        item_id,
        faction,
        unit_price,
        SUM(quantity) AS units_vanished,
        COUNT(*)      AS events
    FROM auction_event_log
    WHERE disappearance_type = 'VANISHED'
    GROUP BY item_id, faction, unit_price
    """,
    """
    CREATE VIEW IF NOT EXISTS v_volume_at_price_daily AS
    SELECT
        item_id,
        faction,
        unit_price,
        (detected_at / 86400) * 86400 AS day_start,
        SUM(quantity) AS units_vanished,
        COUNT(*)      AS events
    FROM auction_event_log
    WHERE disappearance_type = 'VANISHED'
    GROUP BY item_id, faction, unit_price, day_start
    """,
]

_VIEWS_POSTGRES = [
    """
    CREATE OR REPLACE VIEW v_volume_at_price AS
    SELECT
        item_id,
        faction,
        unit_price,
        SUM(quantity) AS units_vanished,
        COUNT(*)      AS events
    FROM auction_event_log
    WHERE disappearance_type = 'VANISHED'
    GROUP BY item_id, faction, unit_price
    """,
    """
    CREATE OR REPLACE VIEW v_volume_at_price_daily AS
    SELECT
        item_id,
        faction,
        unit_price,
        (detected_at / 86400) * 86400 AS day_start,
        SUM(quantity) AS units_vanished,
        COUNT(*)      AS events
    FROM auction_event_log
    WHERE disappearance_type = 'VANISHED'
    GROUP BY item_id, faction, unit_price, day_start
    """,
]


def ensure_views(engine: Engine) -> None:
    stmts = _VIEWS_POSTGRES if engine.dialect.name == "postgresql" else _VIEWS_SQLITE
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))