"""
Database models for the Social Influence Task.

Structure:
  Session  — one participant visit
  Block    — one artwork-rating block (Phase 1 baseline OR Phase 2 influence)
  Rating   — one artwork rating within a block
  Event    — timestamped jsPsych timeline events (instructions shown, etc.)
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    participant_id: Mapped[str] = mapped_column(String, index=True)
    mode: Mapped[str] = mapped_column(String)
    condition_order: Mapped[str | None] = mapped_column(String, nullable=True)
    identity_order: Mapped[str | None] = mapped_column(String, nullable=True)
    sc_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    session_token: Mapped[str] = mapped_column(String, default=_uuid, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monotonic_start_s: Mapped[float | None] = mapped_column(Float, nullable=True)

    blocks: Mapped[list["Block"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    phase: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="blocks")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="block", cascade="all, delete-orphan")


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    block_id: Mapped[str] = mapped_column(ForeignKey("blocks.id"), index=True)
    artwork_id: Mapped[int] = mapped_column(Integer, index=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_type: Mapped[str | None] = mapped_column(String, nullable=True)
    pair_condition: Mapped[str | None] = mapped_column(String, nullable=True)
    agent1_condition: Mapped[str | None] = mapped_column(String, nullable=True)
    agent2_condition: Mapped[str | None] = mapped_column(String, nullable=True)
    agent1_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent2_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    artwork_onset_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    trial_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    block: Mapped["Block"] = relationship(back_populates="ratings")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    block_id: Mapped[str | None] = mapped_column(ForeignKey("blocks.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    t_ms: Mapped[float] = mapped_column(Float)
    t_client_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="events")
