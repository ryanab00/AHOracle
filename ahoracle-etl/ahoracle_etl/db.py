"""Database engine + view bootstrap."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# Load .env from the project root (one level above this package)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def default_db_url() -> str:
    return os.environ.get("AHORACLE_DB_URL", "sqlite:///ahoracle.db")


def make_engine(db_url: str | None = None) -> Engine:
    url = db_url or default_db_url()
    return create_engine(url, future=True)


# ─── Views ────────────────────────────────────────────────────────────────
#
# Same logical views, two dialects.  SQLite uses CREATE VIEW IF NOT EXISTS,
# Postgres uses CREATE OR REPLACE VIEW.

_VIEWS_SQLITE = [
    """
    CREATE VIEW IF NOT EXISTS v_volume_at_price AS
    SELECT
        ael.item_id,
        ael.faction,
        ael.unit_price,
        SUM(ael.quantity)       AS units_vanished,
        COUNT(*)                AS events,
        MIN(ael.detected_at)    AS first_vanished_ts,
        MAX(ael.detected_at)    AS last_vanished_ts,
        SUM(ael.duration_hours) AS total_duration_hours
    FROM auction_event_log ael
    GROUP BY ael.item_id, ael.faction, ael.unit_price
    """,
    """
    CREATE VIEW IF NOT EXISTS v_volume_at_price_daily AS
    SELECT
        ael.item_id,
        ael.faction,
        ael.unit_price,
        ael.detected_at / 86400 AS day_bucket,
        SUM(ael.quantity)       AS units_vanished,
        COUNT(*)                AS events
    FROM auction_event_log ael
    GROUP BY ael.item_id, ael.faction, ael.unit_price, ael.detected_at / 86400
    """,
]

_VIEWS_POSTGRES = [
    """
    CREATE OR REPLACE VIEW v_volume_at_price AS
    SELECT
        ael.item_id,
        ael.faction,
        ael.unit_price,
        SUM(ael.quantity)::bigint       AS units_vanished,
        COUNT(*)::bigint                AS events,
        MIN(ael.detected_at)            AS first_vanished_ts,
        MAX(ael.detected_at)            AS last_vanished_ts,
        SUM(ael.duration_hours)::bigint AS total_duration_hours
    FROM auction_event_log ael
    GROUP BY ael.item_id, ael.faction, ael.unit_price
    """,
    """
    CREATE OR REPLACE VIEW v_volume_at_price_daily AS
    SELECT
        ael.item_id,
        ael.faction,
        ael.unit_price,
        (ael.detected_at / 86400)       AS day_bucket,
        SUM(ael.quantity)::bigint       AS units_vanished,
        COUNT(*)::bigint                AS events
    FROM auction_event_log ael
    GROUP BY ael.item_id, ael.faction, ael.unit_price,
             (ael.detected_at / 86400)
    """,
]


def ensure_views(engine: Engine) -> None:
    dialect = engine.dialect.name
    stmts = _VIEWS_POSTGRES if dialect == "postgresql" else _VIEWS_SQLITE
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))