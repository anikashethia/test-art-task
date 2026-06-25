# Social Influence Task

Artwork rating task measuring social influence susceptibility. Participants
rate each artwork, see the average rating of two named agents, then re-rate.
Influence is operationalized as the shift toward the agents' average rating,
normalised by the maximum possible shift.

Runs **after** the social connection task in the same lab session, with agent
identities and pair assignments passed via URL parameters.

## Structure

```
social-influence-task/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI routes
│   │   ├── models.py        # SQLAlchemy models (Session, Block, Rating, Event)
│   │   ├── db.py            # DB engine / session
│   │   ├── stimuli.py       # Artwork loading & artwork-condition assignment
│   │   ├── pilot.py         # Participant counter (persistent)
│   │   └── stimuli/
│   │       ├── artworks.json       # 50 artwork stimulus definitions
│   │       └── agent_ratings.json  # Pre-generated agent ratings per artwork (add before running)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx          # Entry point — routes to PilotApp or dev App
│   │   ├── App.tsx           # Dev landing screen
│   │   ├── PilotApp.tsx      # Prolific participant orchestrator
│   │   ├── timeline.ts       # jsPsych timeline (Phase 1 + Phase 2)
│   │   ├── api.ts            # API client
│   │   └── components/
│   │       └── TimelineRunner.tsx
│   ├── index.html
│   └── package.json
└── scripts/
    └── csv_to_artworks.py    # Convert stimulus CSV → artworks.json
```

## Task Design

**Trial structure** (per artwork, ~14 s average):
1. **Initial rating** — participant rates artwork on 0–100 slider (self-paced, 10 s cap)
2. **Feedback reveal** — average rating of two named agents shown for 4 s
3. **Re-rating** — participant re-rates the same artwork (self-paced, 10 s cap)
4. **Blank screen** — 500 ms between trials

If the participant does not respond within 10 s, an "Out of time" screen
appears for 2 s and the trial advances without recording a rating.

**4 pair-conditions** (each consisting of 2 named agents):

| Condition | Agents |
|---|---|
| `friendly` | The 2 agents the participant felt connected to |
| `neutral` | The 2 agents the participant felt neutral toward |
| `friendly_control` | Gender/race-matched controls for the friendly pair |
| `neutral_control` | Gender/race-matched controls for the neutral pair |

**Counterbalancing**
- Each artwork appears in exactly one condition per participant
- Condition assignment: `(artwork_id − 1 + participant_index) mod 4`
- Every 4 participants = 1 complete rotation
- Designed for multiples of 4 artworks (e.g. 120 → 30 per condition)

**Influence score (computed at analysis time)**
```
Δ = rerate − initial_rating
normalised_influence = Δ / |avg_agent_rating − initial_rating|
```
Values: 0 = no influence, 1 = full conformity, negative = contrast/reactance.

**Estimated duration:** ~30 min for 120 artworks (range 20–40 min depending on pace).

## Setup

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env: add PROLIFIC_COMPLETION_URL
uv run fastapi dev
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5174 (to avoid port conflict with social
connection task on 5173).

## Before Running Participants

### 1. Populate artworks.json

Use the conversion script to generate artworks.json from the stimulus CSV:

```bash
python scripts/csv_to_artworks.py path/to/stimulus_list.csv --n 50 --out backend/app/stimuli/artworks.json
```

Arguments:
- `csv_path` (positional): path to the stimulus CSV
- `--n`: number of artworks to include (default: 50)
- `--out`: output JSON path (default: `backend/app/stimuli/artworks.json`)

The CSV should have columns: ID, Title, Artist, Year, Medium,
Style / Movement, WikiArt URL, Valence Category, Familiarity Risk.

### 2. Add agent_ratings.json

Create `backend/app/stimuli/agent_ratings.json` with pre-generated agent
ratings for each artwork. Format:

```json
{
  "Alex":   {"1": 72, "2": 45, "3": 68, ...},
  "Sam":    {"1": 60, "2": 38, "3": 55, ...},
  "Casey":  {"1": 65, "2": 50, "3": 60, ...},
  "Jordan": {"1": 58, "2": 42, "3": 52, ...},
  "Morgan": {"1": 70, "2": 48, "3": 62, ...},
  "Riley":  {"1": 55, "2": 40, "3": 58, ...}
}
```

RNG ratings are generated at runtime from fixed seeds — no entry needed.
Without this file, the backend uses deterministic placeholder ratings.

### 3. Image Hosting

Download images from WikiArt and host them. Options:
- **Local**: place in `frontend/public/artworks/1.jpg` and set
  `image_url` to `/artworks/1.jpg`
- **CDN**: upload to S3, Cloudflare R2, or similar and use full URL
- **Dev testing**: leave `image_url` blank — the frontend shows a placeholder

## Prolific Study URL

```
https://yourstudy.com/?mode=pilot
  &PROLIFIC_PID={{%PROLIFIC_PID%}}
  &friendly=Alex,Sam
  &neutral=Casey,Jordan
  &friendly_control=Morgan,Riley
  &neutral_control=Taylor,Drew
  &sc_session_id=<id>
```

- `friendly` / `neutral`: comma-separated pair of agent names the participant
  interacted with in the social connection task (friendly and neutral conditions).
- `friendly_control` / `neutral_control`: gender/race-matched control pairs.
- `sc_session_id`: session ID from the social connection task for cross-task linkage.

All pair parameters fall back to defaults if omitted (useful for dev testing).

## Behavioral Outputs

All data is stored in SQLite (`social_influence.db`). The file is gitignored
and created fresh on first backend startup.

### Tables

**`sessions`** — one row per participant visit

| Column | Description |
|---|---|
| `participant_id` | Prolific PID (or `DEV_USER` in dev mode) |
| `mode` | `pilot` or `dev` |
| `condition_order` | `si_p{index}` — which counterbalancing rotation |
| `identity_order` | JSON object mapping condition → [agent1, agent2] for all 4 pairs |
| `sc_session_id` | Session ID from the social connection task (cross-task linkage) |
| `started_at` | UTC timestamp when session was created |
| `ended_at` | UTC timestamp when `completeSession` was called (null if incomplete) |

**`blocks`** — one row per session (single block, phase=1)

**`ratings`** — two rows per artwork per participant

| Column | Initial rating | Re-rating |
|---|---|---|
| `rating_type` | `"initial"` | `"rerate"` |
| `artwork_id` | ✓ | ✓ |
| `rating` | participant's rating | participant's re-rating |
| `pair_condition` | null | `friendly` / `neutral` / `friendly_control` / `neutral_control` |
| `agent1_condition` | null | name of first agent in pair |
| `agent2_condition` | null | name of second agent in pair |
| `agent1_rating` | null | first agent's pre-set rating for this artwork |
| `agent2_rating` | null | second agent's pre-set rating for this artwork |
| `avg_rating` | null | average of agent1 and agent2 ratings (shown to participant) |
| `artwork_onset_ms` | ms since session start when screen appeared | same |
| `rating_rt_ms` | reaction time from screen onset to submission | same |
| `trial_index` | position in the randomised trial order | same |

**`events`** — full timestamped jsPsych event log

| Event type | When fired |
|---|---|
| `instructions_shown` / `instructions_dismissed` | instruction screen |
| `task_start` | Begin clicked |
| `initial_rating_onset` | initial rating screen appears |
| `initial_rating_response` | initial rating submitted |
| `initial_rating_missed` | 10 s cap reached without response |
| `reveal_onset` / `reveal_end` | feedback screen start/end |
| `rerate_response` | re-rating submitted |
| `rerate_missed` | 10 s cap reached without response |
| `task_end` / `timeline_complete` | end screen |

### Core analysis query

```sql
SELECT
  s.participant_id,
  s.sc_session_id,
  s.condition_order,
  i.artwork_id,
  i.trial_index,
  i.rating                                          AS initial_rating,
  i.rating_rt_ms                                    AS initial_rt_ms,
  r.rating                                          AS rerate,
  r.rating_rt_ms                                    AS rerate_rt_ms,
  r.pair_condition,
  r.agent1_condition,
  r.agent2_condition,
  r.agent1_rating,
  r.agent2_rating,
  r.avg_rating,
  (r.rating - i.rating)                             AS delta,
  (r.rating - i.rating)
    / NULLIF(ABS(r.avg_rating - i.rating), 0)       AS norm_influence
FROM ratings i
JOIN ratings r  ON i.block_id = r.block_id
                AND i.artwork_id = r.artwork_id
                AND i.rating_type = 'initial'
                AND r.rating_type = 'rerate'
JOIN blocks b   ON i.block_id = b.id
JOIN sessions s ON b.session_id = s.id
ORDER BY s.participant_id, i.trial_index;
```

`norm_influence` is NULL when the participant's initial rating exactly matches
the average shown (no room to move), and should be excluded from analysis.
