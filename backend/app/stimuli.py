"""
Stimuli management for the Social Influence Task.

Each trial shows two agents' ratings and their average. There are four
pair-conditions, each consisting of two named agents:

  friendly          — the two agents the participant felt connected to
  neutral           — the two agents the participant felt neutral toward
  friendly_control  — gender/race-matched controls for the friendly pair
  neutral_control   — gender/race-matched controls for the neutral pair

Artwork-condition assignment:
  4 conditions, N artworks (ideally a multiple of 4)
  Rotation: every 4 participants = 1 complete rotation
  Rule: (artwork_id − 1 + participant_index) mod 4 → condition
"""

import json
import random
from pathlib import Path

STIMULI_DIR = Path(__file__).parent / "stimuli"
ARTWORKS_FILE = STIMULI_DIR / "artworks.json"
AGENT_RATINGS_FILE = STIMULI_DIR / "agent_ratings.json"

CONDITION_TYPES = ["friendly", "neutral", "friendly_control", "neutral_control"]
N_CONDITIONS = len(CONDITION_TYPES)

# Fallback pairs used in dev mode when no pairs are supplied
DEFAULT_PAIRS: dict[str, tuple[str, str]] = {
    "friendly":         ("Alex", "Sam"),
    "neutral":          ("Casey", "Jordan"),
    "friendly_control": ("Morgan", "Riley"),
    "neutral_control":  ("Taylor", "Drew"),
}


def load_artworks() -> list[dict]:
    return json.loads(ARTWORKS_FILE.read_text())


def load_agent_ratings() -> dict[str, dict[str, int]]:
    if AGENT_RATINGS_FILE.exists():
        return json.loads(AGENT_RATINGS_FILE.read_text())
    return {}


def get_agent_rating(agent: str, artwork_id: int, ratings: dict) -> int:
    agent_ratings = ratings.get(agent, {})
    rating = agent_ratings.get(str(artwork_id))
    if rating is not None:
        return int(rating)
    rng = random.Random(hash(agent) + artwork_id)
    return rng.randint(30, 80)


def assign_artworks_to_conditions(participant_index: int) -> dict[str, list[dict]]:
    artworks = load_artworks()
    offset = participant_index % N_CONDITIONS
    assignment: dict[str, list[dict]] = {c: [] for c in CONDITION_TYPES}
    for artwork in artworks:
        condition_idx = ((artwork["id"] - 1) + offset) % N_CONDITIONS
        condition = CONDITION_TYPES[condition_idx]
        assignment[condition].append(artwork)
    return assignment


def build_trials(
    participant_index: int,
    pairs: dict[str, tuple[str, str]] | None = None,
    seed: int | None = None,
) -> list[dict]:
    if pairs is None:
        pairs = DEFAULT_PAIRS

    assignment = assign_artworks_to_conditions(participant_index)
    ratings = load_agent_ratings()

    trials = []
    for condition, artworks in assignment.items():
        agent1, agent2 = pairs.get(condition, DEFAULT_PAIRS[condition])
        for artwork in artworks:
            r1 = get_agent_rating(agent1, artwork["id"], ratings)
            r2 = get_agent_rating(agent2, artwork["id"], ratings)
            avg = round((r1 + r2) / 2)
            trials.append({
                "artwork_id": artwork["id"],
                "title": artwork["title"],
                "artist": artwork["artist"],
                "year": artwork["year"],
                "image_url": artwork.get("image_url", ""),
                "wikiart_url": artwork.get("wikiart_url", ""),
                "pair_condition": condition,
                "agent1": agent1,
                "agent2": agent2,
                "agent1_rating": r1,
                "agent2_rating": r2,
                "avg_rating": avg,
            })

    rng = random.Random(seed if seed is not None else participant_index)
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i

    return trials
