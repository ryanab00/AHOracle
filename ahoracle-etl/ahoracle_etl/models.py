"""SQLAlchemy models for the AHOracle warehouse."""
from sqlalchemy import (
    BigInteger, Integer, String, Float, Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Auto-incrementing PK that's BIGINT on Postgres, INTEGER on SQLite.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


# ─── Hot storage ─────────────────────────────────────────────────────────

class LiveAuctionBook(Base):
    __tablename__ = "live_auction_book"

    id:                Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_timestamp:    Mapped[int] = mapped_column(BigInteger, index=True)
    faction:           Mapped[str] = mapped_column(String(10), index=True)
    item_id:           Mapped[int] = mapped_column(Integer, index=True)
    item_name:         Mapped[str] = mapped_column(String(100), nullable=True)
    seller:            Mapped[str] = mapped_column(String(50), nullable=True)
    stack_size:        Mapped[int] = mapped_column(Integer)
    unit_buyout_price: Mapped[int] = mapped_column(Integer)
    duration_hours:    Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_lab_faction_item_ts", "faction", "item_id", "scan_timestamp"),
    )


# ─── Dimension ───────────────────────────────────────────────────────────

class DimItem(Base):
    __tablename__ = "dim_items"

    item_id:        Mapped[int] = mapped_column(Integer, primary_key=True)
    item_name:      Mapped[str] = mapped_column(String(100), nullable=True)
    max_stack_size: Mapped[int] = mapped_column(Integer, nullable=True)
    quality:        Mapped[str] = mapped_column(String(20), nullable=True)


# ─── Cold storage: vanished listings ─────────────────────────────────────

class AuctionEventLog(Base):
    __tablename__ = "auction_event_log"

    event_id:                     Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    item_id:                      Mapped[int] = mapped_column(Integer, index=True)
    faction:                      Mapped[str] = mapped_column(String(10), index=True)
    seller:                       Mapped[str] = mapped_column(String(50), nullable=True)
    unit_price:                   Mapped[int] = mapped_column(Integer)
    quantity:                     Mapped[int] = mapped_column(Integer)
    duration_hours:               Mapped[int] = mapped_column(Integer, nullable=True)
    first_seen:                   Mapped[int] = mapped_column(BigInteger, nullable=True)
    last_seen:                    Mapped[int] = mapped_column(BigInteger, nullable=True)
    detected_at:                  Mapped[int] = mapped_column(BigInteger, index=True)
    detection_resolution_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    disappearance_type:           Mapped[str] = mapped_column(String(20), default="VANISHED")
    confidence:                   Mapped[float] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_ael_item_faction_ts", "item_id", "faction", "detected_at"),
    )


# ─── Cold storage: OHLCV per hour ────────────────────────────────────────

class OHLCVSession(Base):
    __tablename__ = "ohlcv_session"

    bucket_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id:      Mapped[int] = mapped_column(Integer, primary_key=True)
    faction:      Mapped[str] = mapped_column(String(10), primary_key=True)
    open_price:   Mapped[int] = mapped_column(Integer)
    high_price:   Mapped[int] = mapped_column(Integer)
    low_price:    Mapped[int] = mapped_column(Integer)
    close_price:  Mapped[int] = mapped_column(Integer)
    volume:       Mapped[int] = mapped_column(Integer, default=0)


# ─── Book-keeping ────────────────────────────────────────────────────────

class ScanLog(Base):
    __tablename__ = "scan_log"

    faction:        Mapped[str] = mapped_column(String(10), primary_key=True)
    scan_timestamp: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    zone:           Mapped[str] = mapped_column(String(50))
    listing_count:  Mapped[int] = mapped_column(Integer)
    ingested_at:    Mapped[int] = mapped_column(BigInteger)


class ScanSnapshot(Base):
    __tablename__ = "scan_snapshots"

    id:                Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    scan_timestamp:    Mapped[int] = mapped_column(BigInteger, index=True)
    faction:           Mapped[str] = mapped_column(String(10), index=True)
    zone:              Mapped[str] = mapped_column(String(50), nullable=True)
    item_id:           Mapped[int] = mapped_column(Integer, index=True)
    item_name:         Mapped[str] = mapped_column(String(100), nullable=True)
    seller:            Mapped[str] = mapped_column(String(50), nullable=True)
    stack_size:        Mapped[int] = mapped_column(Integer)
    unit_buyout_price: Mapped[int] = mapped_column(Integer)
    duration_hours:    Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_snap_faction_ts", "faction", "scan_timestamp"),
    )