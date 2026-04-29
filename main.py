"""
Social Influence Task — FastAPI Backend

Endpoints mirror the social connection task structure:
  POST /sessions                          — create session, assign participant index
  POST /sessions/{id}/blocks              — start a rating block (phase 1 or 2)
  POST /sessions/{id}/blocks/{bid}/ratings — submit a single artwork rating
  POST /sessions/{id}/events              — log a jsPsych timeline event
  POST /sessions/{id}/triggers            — log a scanner TR pulse
  GET  /sessions/{id}/assignment          — return this participant's artwork-condition assignment
  POST /sessions/{id}/complete            — stamp ended_at, return Prolific URL
  GET  /health                            — health check
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

load_dotenv()

from .db import Base, engine, get_db
from . import models
from .stimuli import build_phase1_trials, build_phase2_trials
from .pilot import assign_participant_index, ParticipantCounter


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Social Influence Task — Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROLIFIC_COMPLETION_URL = os.getenv("PROLIFIC_COMPLETION_URL", "")


# ── Clock ─────────────────────────────────────────────────────────────────────

def session_local_ms(session: models.Session, monotonic_s: float | None = None) -> float:
    """Convert time.monotonic() (or now) to session-local ms."""
    if session.monotonic_start_s is None:
        return 0.0
    t = monotonic_s if monotonic_s is not None else time.monotonic()
    return (t - session.monotonic_start_s) * 1000.0


# ── Auth ──────────────────────────────────────────────────────────────────────

def require_session_token(
    session_id: str,
    authorization: str | None = Header(None),
    db: DBSession = Depends(get_db),
) -> models.Session:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.get(models.Session, session_id)
    if session is None or session.session_token != token:
        raise HTTPException(status_code=401, detail="Invalid session token")
    return session


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateSessionBody(BaseModel):
    participant_id: str
    mode: Literal["pilot", "scanner", "dev"] = "dev"


class CreateSessionResponse(BaseModel):
    session_id: str
    session_token: str
    participant_index: int
    # Pre-computed Phase 2 trial list so the frontend doesn't need to call
    # /assignment separately. Includes agent_condition and agent_rating per trial.
    phase2_trials: list[dict]
    # Phase 1 trial list — same artworks, shuffled differently, no agent info.
    phase1_trials: list[dict]


class CreateBlockBody(BaseModel):
    phase: int = Field(ge=1, le=2)


class CreateBlockResponse(BaseModel):
    block_id: str


class SubmitRatingBody(BaseModel):
    artwork_id: int
    rating: float = Field(ge=0, le=100)
    agent_condition: str | None = None   # Phase 2 only
    agent_rating: float | None = None    # Phase 2 only
    artwork_onset_ms: float | None = None
    rating_rt_ms: float | None = None
    trial_index: int | None = None
    t_client_ms: float | None = None


class SubmitRatingResponse(BaseModel):
    rating_id: str


class LogEventBody(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    block_id: str | None = None
    t_client_ms: float | None = None
    payload: dict | None = None


class LogEventResponse(BaseModel):
    event_id: str
    t_ms: float


class LogTriggerBody(BaseModel):
    tr_number: int = Field(ge=0)
    t_client_ms: float | None = None


class LogTriggerResponse(BaseModel):
    trigger_id: str
    t_ms: float


class CompleteSessionResponse(BaseModel):
    prolific_completion_url: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(body: CreateSessionBody, db: DBSession = Depends(get_db)):
    # Assign participant index (persistent counter)
    if body.mode == "pilot":
        participant_index = assign_participant_index(db)
    else:
        # Dev mode: use 0 for testing
        participant_index = 0

    # Artwork-condition assignment and trial lists
    phase1_trials = build_phase1_trials(participant_index)
    phase2_trials = build_phase2_trials(participant_index)

    session = models.Session(
        participant_id=body.participant_id,
        mode=body.mode,
        condition_order=f"participant_{participant_index}",
        monotonic_start_s=time.monotonic(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return CreateSessionResponse(
        session_id=session.id,
        session_token=session.session_token,
        participant_index=participant_index,
        phase1_trials=phase1_trials,
        phase2_trials=phase2_trials,
    )


@app.post("/sessions/{session_id}/blocks", response_model=CreateBlockResponse)
def create_block(
    session_id: str,
    body: CreateBlockBody,
    session: models.Session = Depends(require_session_token),
    db: DBSession = Depends(get_db),
):
    block = models.Block(
        session_id=session.id,
        phase=body.phase,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return CreateBlockResponse(block_id=block.id)


@app.post(
    "/sessions/{session_id}/blocks/{block_id}/ratings",
    response_model=SubmitRatingResponse,
)
def submit_rating(
    session_id: str,
    block_id: str,
    body: SubmitRatingBody,
    session: models.Session = Depends(require_session_token),
    db: DBSession = Depends(get_db),
):
    block = db.get(models.Block, block_id)
    if block is None or block.session_id != session.id:
        raise HTTPException(status_code=404, detail="Block not found")

    t_ms = body.t_client_ms if body.t_client_ms is not None else session_local_ms(session)

    rating = models.Rating(
        block_id=block_id,
        artwork_id=body.artwork_id,
        rating=body.rating,
        agent_condition=body.agent_condition,
        agent_rating=body.agent_rating,
        artwork_onset_ms=body.artwork_onset_ms,
        rating_rt_ms=body.rating_rt_ms,
        trial_index=body.trial_index,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return SubmitRatingResponse(rating_id=rating.id)


@app.post("/sessions/{session_id}/events", response_model=LogEventResponse)
def log_event(
    session_id: str,
    body: LogEventBody,
    session: models.Session = Depends(require_session_token),
    db: DBSession = Depends(get_db),
):
    if body.block_id is not None:
        block = db.get(models.Block, body.block_id)
        if block is None or block.session_id != session.id:
            raise HTTPException(status_code=404, detail="Block not found")

    t_ms = body.t_client_ms if body.t_client_ms is not None else session_local_ms(session)
    ev = models.Event(
        session_id=session.id,
        block_id=body.block_id,
        type=body.type,
        t_ms=t_ms,
        t_client_ms=body.t_client_ms,
        payload=body.payload,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return LogEventResponse(event_id=ev.id, t_ms=t_ms)


@app.post("/sessions/{session_id}/triggers", response_model=LogTriggerResponse)
def log_trigger(
    session_id: str,
    body: LogTriggerBody,
    session: models.Session = Depends(require_session_token),
    db: DBSession = Depends(get_db),
):
    t_ms = body.t_client_ms if body.t_client_ms is not None else session_local_ms(session)
    tr = models.Trigger(
        session_id=session.id,
        tr_number=body.tr_number,
        t_ms=t_ms,
        t_client_ms=body.t_client_ms,
    )
    db.add(tr)
    db.commit()
    db.refresh(tr)
    return LogTriggerResponse(trigger_id=tr.id, t_ms=t_ms)


@app.post("/sessions/{session_id}/complete", response_model=CompleteSessionResponse)
def complete_session(
    session_id: str,
    session: models.Session = Depends(require_session_token),
    db: DBSession = Depends(get_db),
):
    from datetime import datetime, timezone
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    return CompleteSessionResponse(prolific_completion_url=PROLIFIC_COMPLETION_URL)
