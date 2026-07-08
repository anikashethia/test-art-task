#!/usr/bin/env python3
"""
Diagnostic dump for a single session's trial data.

Usage:
    python backend/scripts/dump_session.py --session SESSION_ID [--db PATH] [--verify]
    python backend/scripts/dump_session.py --participant PARTICIPANT_ID [--db PATH] [--verify]

Outputs CSV to stdout. Pass --verify to also print balance/reconstruction checks.
"""

import argparse
import csv
import os
import sqlite3
import sys
from collections import defaultdict

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "social_influence.db")

DUMP_SQL = """
SELECT
    ri.trial_index,
    ri.artwork_id,
    rr.pair_condition,
    rr.agent1_condition,
    rr.agent2_condition,
    ri.rating              AS initial_rating,
    rr.offset_magnitude,
    rr.offset_sign,
    rr.offset_sign_flipped,
    rr.base_offset_index,
    rr.avg_rating,
    rr.rating              AS rerate,
    ri.rating_rt_ms        AS initial_rt_ms,
    rr.rating_rt_ms        AS rerate_rt_ms
FROM ratings ri
JOIN ratings rr
    ON ri.block_id   = rr.block_id
   AND ri.artwork_id = rr.artwork_id
   AND rr.rating_type = 'rerate'
WHERE ri.rating_type = 'initial'
  AND ri.block_id IN (
      SELECT id FROM blocks WHERE session_id = ?
  )
ORDER BY ri.trial_index
"""


def resolve_session(conn: sqlite3.Connection, args: argparse.Namespace) -> str:
    if args.session:
        return args.session
    row = conn.execute(
        "SELECT id FROM sessions WHERE participant_id = ? ORDER BY started_at DESC LIMIT 1",
        (args.participant,),
    ).fetchone()
    if row is None:
        sys.exit(f"No session found for participant_id={args.participant}")
    return row["id"]


def clip(val: float) -> float:
    return max(0.0, min(100.0, val))


def run_verify(rows: list[dict]) -> None:
    print("\n" + "=" * 60, file=sys.stderr)
    print("VERIFICATION CHECKS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    conditions = sorted({r["pair_condition"] for r in rows if r["pair_condition"]})
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["pair_condition"]:
            by_cond[r["pair_condition"]].append(r)

    all_passed = True

    # ── Check 1: Balance ─────────────────────────────────────────────────────
    print("\n[1] Balance check (mean magnitude & +/- count per condition)", file=sys.stderr)
    n_per_cond = max((len(by_cond[c]) for c in conditions), default=0)
    is_full_mode = n_per_cond >= 30
    if not is_full_mode:
        print(
            f"  NOTE: {n_per_cond} trials/condition — balance is only guaranteed at n=30 (full mode).",
            file=sys.stderr,
        )
    cond_stats: dict[str, dict] = {}
    for cond in conditions:
        cr = by_cond[cond]
        mags = [r["offset_magnitude"] for r in cr if r["offset_magnitude"] is not None]
        signs = [r["offset_sign"] for r in cr if r["offset_sign"] is not None]
        cond_stats[cond] = {
            "n": len(cr),
            "mean_mag": sum(mags) / len(mags) if mags else None,
            "pos": sum(1 for s in signs if s == 1),
            "neg": sum(1 for s in signs if s == -1),
        }
        mm = cond_stats[cond]["mean_mag"]
        print(
            f"  {cond:20s}  n={len(cr):3d}  mean_mag={'n/a' if mm is None else f'{mm:.2f}'}"
            f"  pos={cond_stats[cond]['pos']}  neg={cond_stats[cond]['neg']}",
            file=sys.stderr,
        )
    mean_mags = [s["mean_mag"] for s in cond_stats.values() if s["mean_mag"] is not None]
    if not mean_mags:
        print("  (no offset_magnitude data — pre-offset session)", file=sys.stderr)
    elif not is_full_mode:
        print("  (skipped — only meaningful in full mode)", file=sys.stderr)
    elif (max(mean_mags) - min(mean_mags)) < 1.0:
        print("  ✓ Mean magnitudes are within 1 point across all conditions", file=sys.stderr)
    else:
        print("  ✗ Mean magnitude imbalance detected!", file=sys.stderr)
        all_passed = False

    # ── Check 2: Reconstruction ───────────────────────────────────────────────
    print("\n[2] Reconstruction check (avg_rating == clip(initial + sign * mag))", file=sys.stderr)
    mismatches = []
    for r in rows:
        if None in (r["initial_rating"], r["offset_sign"], r["offset_magnitude"], r["avg_rating"]):
            continue
        expected = round(clip(r["initial_rating"] + r["offset_sign"] * r["offset_magnitude"]))
        if abs(expected - r["avg_rating"]) > 0.5:
            mismatches.append({**r, "expected": expected})
    rows_with_data = [r for r in rows if None not in (r["initial_rating"], r["offset_sign"], r["offset_magnitude"], r["avg_rating"])]
    if not rows_with_data:
        print("  (no offset data — pre-offset session)", file=sys.stderr)
    elif not mismatches:
        print(f"  ✓ All {len(rows_with_data)} rows pass the reconstruction formula", file=sys.stderr)
    else:
        print(f"  ✗ {len(mismatches)} mismatch(es) found:", file=sys.stderr)
        for m in mismatches:
            print(
                f"    trial={m['trial_index']} artwork={m['artwork_id']} "
                f"initial={m['initial_rating']} sign={m['offset_sign']} "
                f"mag={m['offset_magnitude']} expected={m['expected']} got={m['avg_rating']}",
                file=sys.stderr,
            )
        all_passed = False

    # ── Check 3: Base set reuse ───────────────────────────────────────────────
    print("\n[3] Base set reuse check (same base_offset_index set across conditions)", file=sys.stderr)
    if not is_full_mode:
        print(
            f"  NOTE: {n_per_cond} trials/condition — base set reuse check only meaningful at n=30 (full mode).",
            file=sys.stderr,
        )
    # Use base_offset_index (not offset_sign, which depends on initial_rating)
    cond_indices: dict[str, list] = {}
    for cond in conditions:
        cond_indices[cond] = sorted(
            r["base_offset_index"] for r in by_cond[cond] if r["base_offset_index"] is not None
        )
    ref_cond = conditions[0]
    for cond in conditions[1:]:
        if not is_full_mode:
            print(f"  (skipped — only meaningful in full mode)", file=sys.stderr)
            break
        if cond_indices[cond] == cond_indices[ref_cond]:
            print(f"  ✓ {cond} has same base_offset_index set as {ref_cond}", file=sys.stderr)
        else:
            print(f"  ✗ {cond} differs from {ref_cond}!", file=sys.stderr)
            all_passed = False

    # ── Check 4: Reproducibility reminder ────────────────────────────────────
    print("\n[4] Reproducibility check (precomputed fields only)", file=sys.stderr)
    print(
        "  offset_magnitude and base_offset_index are fixed at session creation.\n"
        "  offset_sign and avg_rating legitimately vary with initial_rating.\n"
        "  To verify: dump two sessions for the same participant and diff offset_magnitude + base_offset_index.",
        file=sys.stderr,
    )

    # ── Check 5: Flip concentration ───────────────────────────────────────────
    print("\n[5] Flip concentration check (offset_sign_flipped by condition)", file=sys.stderr)
    for cond in conditions:
        cr = by_cond[cond]
        flips = [r for r in cr if r["offset_sign_flipped"]]
        print(
            f"  {cond:20s}  flipped={len(flips)}/{len(cr)}"
            f"  ({100 * len(flips) / len(cr):.0f}%)",
            file=sys.stderr,
        )
    flip_counts = [len([r for r in by_cond[c] if r["offset_sign_flipped"]]) for c in conditions]
    if max(flip_counts, default=0) - min(flip_counts, default=0) <= 3:
        print("  ✓ Flip counts are balanced across conditions", file=sys.stderr)
    else:
        print("  ✗ Flips appear concentrated — check boundary conditions", file=sys.stderr)
        all_passed = False

    print("\n" + ("✓ ALL CHECKS PASSED" if all_passed else "✗ SOME CHECKS FAILED"), file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump a session's trial data as CSV")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", help="session_id UUID")
    group.add_argument("--participant", help="participant_id string")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to SQLite DB file")
    parser.add_argument("--verify", action="store_true", help="run verification checks after dump")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"DB not found: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    session_id = resolve_session(conn, args)
    meta = conn.execute(
        "SELECT participant_id, mode FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    print(f"# session_id:    {session_id}", file=sys.stderr)
    if meta:
        print(f"# participant_id: {meta['participant_id']}  mode: {meta['mode']}", file=sys.stderr)

    rows = [dict(r) for r in conn.execute(DUMP_SQL, (session_id,)).fetchall()]

    if not rows:
        sys.exit(f"No rerate rows found for session {session_id} — session may be incomplete")

    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    print(f"\n# {len(rows)} trials written", file=sys.stderr)

    if args.verify:
        run_verify(rows)


if __name__ == "__main__":
    main()
