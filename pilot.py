"""
Pilot participant counter for the Social Influence Task.

Mirrors the pattern in the social connection task's pilot.py:
  - Maintains a persistent counter in the DB (single-row table)
  - Each new pilot participant gets the next index
  - Index drives artwork-condition assignment (participant_index mod 5)

The counter survives server restarts. For a multi-worker deployment, wrap the
read-increment-write in a SELECT ... FOR UPDATE or use a DB-level sequence.
"""

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class ParticipantCounter(Base):
    """Single-row table tracking total enrolled pilot participants."""

    __tablename__ = "participant_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    next_index: Mapped[int] = mapped_column(Integer, default=0)


def assign_participant_index(db: DBSession) -> int:
    """
    Fetch (or create) the counter row, read the current index, increment, commit.

    Returns the 0-based participant index for this participant.
    Caller uses this to derive artwork-condition assignments.
    """
    counter = db.get(ParticipantCounter, 1)
    if counter is None:
        counter = ParticipantCounter(id=1, next_index=0)
        db.add(counter)
        db.flush()

    index = counter.next_index
    counter.next_index = index + 1
    db.flush()

    return index
