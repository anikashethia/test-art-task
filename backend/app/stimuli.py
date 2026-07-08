"""
Stimuli management for the Social Influence Task.

Avatars are identified by their canonical id: {race}_{gender}_{name}
  e.g. r1_m_alex, r2_f_jamie

Four pair-conditions per participant (from counterbalancing.json):
  friendly          — friendly male + friendly female
  neutral           — neutral male + neutral female
  friendly_control  — opposite-gender, same-race controls for friendly pair
  neutral_control   — opposite-gender, same-race controls for neutral pair

Artwork-condition assignment:
  4 conditions, artworks assigned by (artwork_id - 1 + participant_index) mod 4
  Every 4 participants = 1 complete rotation
"""

import json
import random
from pathlib import Path

STIMULI_DIR     = Path(__file__).parent / "stimuli"
ARTWORKS_FILE   = STIMULI_DIR / "artworks.json"
CB_FILE         = Path(__file__).parent / "counterbalancing.json"

CONDITION_TYPES = ["friendly", "neutral", "friendly_control", "neutral_control"]
N_CONDITIONS    = len(CONDITION_TYPES)

# Offset design constants
OFFSET_N      = 30   # offsets per condition (= artworks per condition in full mode)
OFFSET_MAG_LO = 20
OFFSET_MAG_HI = 35
OFFSET_N_POS  = 15   # exactly half positive, half negative

# Avatar dicts used in dev mode (config 1 values)
DEFAULT_PAIRS: dict[str, tuple[dict, dict]] = {
    "friendly":         ({"name": "Jordan", "id": "r1_m_jordan"}, {"name": "Sam",   "id": "r4_f_sam"}),
    "neutral":          ({"name": "Elliot", "id": "r3_m_elliot"}, {"name": "Parker","id": "r2_f_parker"}),
    "friendly_control": ({"name": "Alex",   "id": "r1_m_alex"},   {"name": "Rowan", "id": "r4_f_rowan"}),
    "neutral_control":  ({"name": "Casey",  "id": "r3_m_casey"},  {"name": "Jamie", "id": "r2_f_jamie"}),
}


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_artworks() -> list[dict]:
    return json.loads(ARTWORKS_FILE.read_text())


def load_counterbalancing() -> list[dict]:
    return json.loads(CB_FILE.read_text())


# ── Counterbalancing lookup ───────────────────────────────────────────────────

def get_pairs_for_config(config_index: int) -> dict[str, tuple[dict, dict]]:
    """Return the 4 avatar pairs for a 0-based config index (0–23)."""
    table = load_counterbalancing()
    entry = table[config_index % len(table)]
    return {
        "friendly": (
            {"name": entry["friendly_male"]["name"],   "id": entry["friendly_male"]["id"]},
            {"name": entry["friendly_female"]["name"], "id": entry["friendly_female"]["id"]},
        ),
        "neutral": (
            {"name": entry["neutral_male"]["name"],   "id": entry["neutral_male"]["id"]},
            {"name": entry["neutral_female"]["name"], "id": entry["neutral_female"]["id"]},
        ),
        "friendly_control": (
            {"name": entry["friendly_male_control"]["name"],   "id": entry["friendly_male_control"]["id"]},
            {"name": entry["friendly_female_control"]["name"], "id": entry["friendly_female_control"]["id"]},
        ),
        "neutral_control": (
            {"name": entry["neutral_male_control"]["name"],   "id": entry["neutral_male_control"]["id"]},
            {"name": entry["neutral_female_control"]["name"], "id": entry["neutral_female_control"]["id"]},
        ),
    }


# ── Participant-relative offset precomputation ────────────────────────────────

def build_base_offsets(participant_index: int) -> list[tuple[int, int]]:
    """30 (magnitude, sign) pairs seeded by participant_index.
    Exactly OFFSET_N_POS positive and OFFSET_N_POS negative entries."""
    rng = random.Random(participant_index)
    magnitudes = [rng.randint(OFFSET_MAG_LO, OFFSET_MAG_HI) for _ in range(OFFSET_N)]
    signs = [1] * OFFSET_N_POS + [-1] * (OFFSET_N - OFFSET_N_POS)
    rng.shuffle(signs)
    return list(zip(magnitudes, signs))


def get_condition_offsets(
    participant_index: int, condition: str, n: int
) -> list[tuple[int, int, int]]:
    """Return n (base_offset_index, magnitude, sign) triples for one condition.
    Draws from the participant's base set shuffled independently per condition,
    so every condition has the same underlying distribution.
    base_offset_index is the position in the original base set, for auditability."""
    base = build_base_offsets(participant_index)
    indexed = list(enumerate(base))  # [(original_idx, (magnitude, sign)), ...]
    rng = random.Random(participant_index + hash(condition))
    rng.shuffle(indexed)
    return [(idx, mag, sign) for idx, (mag, sign) in indexed[:n]]


# ── Artwork assignment ────────────────────────────────────────────────────────

def assign_artworks_to_conditions(participant_index: int) -> dict[str, list[dict]]:
    artworks = load_artworks()
    offset   = participant_index % N_CONDITIONS
    assignment: dict[str, list[dict]] = {c: [] for c in CONDITION_TYPES}
    for artwork in artworks:
        condition_idx = ((artwork["id"] - 1) + offset) % N_CONDITIONS
        assignment[CONDITION_TYPES[condition_idx]].append(artwork)
    return assignment


# ── Trial builder ─────────────────────────────────────────────────────────────

def build_trials(
    participant_index: int,
    pairs: dict[str, tuple[dict, dict]] | None = None,
    seed: int | None = None,
    trial_limit: int | None = None,
) -> list[dict]:
    if pairs is None:
        pairs = DEFAULT_PAIRS

    assignment = assign_artworks_to_conditions(participant_index)

    per_condition: int | None = None
    if trial_limit is not None:
        per_condition = trial_limit // N_CONDITIONS

    trials = []
    for condition, artworks in assignment.items():
        agent1, agent2 = pairs.get(condition, DEFAULT_PAIRS[condition])

        if per_condition is not None:
            condition_rng = random.Random(
                (seed if seed is not None else participant_index) + hash(condition)
            )
            artworks = condition_rng.sample(artworks, min(per_condition, len(artworks)))

        offsets = get_condition_offsets(participant_index, condition, len(artworks))

        for i, artwork in enumerate(artworks):
            base_idx, magnitude, sign = offsets[i]
            trials.append({
                "artwork_id":         artwork["id"],
                "title":              artwork["title"],
                "artist":             artwork["artist"],
                "year":               artwork["year"],
                "image_url":          artwork.get("image_url", ""),
                "wikiart_url":        artwork.get("wikiart_url", ""),
                "pair_condition":     condition,
                "agent1":             agent1["name"],
                "agent1_code":        agent1["id"],
                "agent2":             agent2["name"],
                "agent2_code":        agent2["id"],
                "offset_magnitude":   magnitude,
                "offset_sign":        sign,
                "base_offset_index":  base_idx,
            })

    rng = random.Random(seed if seed is not None else participant_index)
    rng.shuffle(trials)
    for i, t in enumerate(trials):
        t["trial_index"] = i

    return trials
