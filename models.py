"""
Database models for the Social Influence Task.

Structure mirrors the social connection task codebase:
  Session  — one participant visit
  Block    — one artwork-rating block (Phase 1 baseline OR Phase 2 influence)
  Rating   — one artwork rating within a block
  Event    — timestamped jsPsych timeline events (instructions shown, etc.)
  Trigger  — scanner TR pulses (scanner mode only)

Phase 1 (baseline): participants rate ~75 artworks before any agent interaction.
Phase 2 (influence): participants re-rate artworks after seeing an agent's rating.
  Each artwork is assigned to exactly one agent condition (or RNG) per participant,
  determined by the rotation table (rotations/pilot.json).
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Float, JSON, Boolean
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
    # 'pilot' | 'scanner' | 'dev'
    mode: Mapped[str] = mapped_column(String)
    # Serialised rotation assignment, e.g. "config_3_FN" — matches social
    # connection task convention for cross-task linkage.
    condition_order: Mapped[str | None] = mapped_column(String, nullable=True)
    session_token: Mapped[str] = mapped_column(String, default=_uuid, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Monotonic anchor — same clock convention as social connection task so
    # events from both tasks can be merged by participant_id at analysis time.
    monotonic_start_s: Mapped[float | None] = mapped_column(Float, nullable=True)

    blocks: Mapped[list["Block"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    triggers: Mapped[list["Trigger"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Block(Base):
    """
    One rating block — either Phase 1 (baseline) or Phase 2 (influence).

    phase: 1 = baseline rating before agent interactions
           2 = influence rating after agent interactions (post-scan in scanner version)
    """
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    # 1 = baseline (Phase 1), 2 = influence (Phase 2)
    phase: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="blocks")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="block", cascade="all, delete-orphan")


class Rating(Base):
    """
    One artwork rating within a block.

    Phase 1: agent_identity and agent_rating are NULL (participant rates blind).
    Phase 2: agent_identity is set (e.g. "Alex", "Sam", "RNG"), agent_rating
             is the rating shown to the participant. influence_score is computed
             at analysis time as:
               Δ = phase2_rating − phase1_rating
               normalised = Δ / |agent_rating − phase1_rating|
    """
    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    block_id: Mapped[str] = mapped_column(ForeignKey("blocks.id"), index=True)
    # Artwork identifier — matches artwork_id in stimuli/artworks.json
    artwork_id: Mapped[int] = mapped_column(Integer, index=True)
    # Participant's rating (0–100 continuous slider)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Phase 2 only: which agent condition this artwork was assigned to
    agent_condition: Mapped[str | None] = mapped_column(String, nullable=True)  # 'Alex'|'Sam'|'Casey'|'Jordan'|'RNG'
    # Phase 2 only: the rating shown to the participant
    agent_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Timing — session-local ms, same clock as social connection task
    artwork_onset_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Trial position within the block
    trial_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    block: Mapped["Block"] = relationship(back_populates="ratings")


class Event(Base):
    """Timestamped jsPsych timeline events — mirrors social connection task."""
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    block_id: Mapped[str | None] = mapped_column(ForeignKey("blocks.id"), nullable=True, index=True)
    # e.g. 'instructions_shown', 'phase1_start', 'phase2_start',
    #      'artwork_onset', 'rating_response', 'iti_onset', 'block_end'
    type: Mapped[str] = mapped_column(String, index=True)
    t_ms: Mapped[float] = mapped_column(Float)          # session-local ms
    t_client_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="events")


class Trigger(Base):
    """Scanner TR pulses — mirrors social connection task."""
    __tablename__ = "triggers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    tr_number: Mapped[int] = mapped_column(Integer)
    t_ms: Mapped[float] = mapped_column(Float)
    t_client_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="triggers")
