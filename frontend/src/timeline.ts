/**
 * Social Influence Task — jsPsych Timeline
 *
 * Two-phase structure:
 *   Phase 1 (baseline): ~75 artwork ratings, no agent info shown.
 *   Phase 2 (influence): ~75 artwork ratings, each preceded by agent's rating.
 *
 * Trial structure per Phase 2 trial (from design doc):
 *   1. Artwork + agent rating reveal (4 s)
 *   2. Re-rating: participant rates on 0–100 slider (self-paced, ≤8 s)
 *   3. ITI: fixation cross (2–4 s jittered)
 *
 * Phase 1 trials use the same slider, no reveal step.
 *
 * Scanner mode: waits for first TR ('5' keypress) before starting.
 */

import type { JsPsych } from "jspsych";
import HtmlButtonResponse from "@jspsych/plugin-html-button-response";
import HtmlSliderResponse from "@jspsych/plugin-html-slider-response";
import HtmlKeyboardResponse from "@jspsych/plugin-html-keyboard-response";
import {
  createBlock,
  submitRating,
  postEvent,
  type Artwork,
  type Phase2Trial,
  type Mode,
} from "./api";

// ── Context ───────────────────────────────────────────────────────────────────

export type TaskContext = {
  sessionId: string;
  token: string;
  mode: Mode;
  phase1Trials: Artwork[];
  phase2Trials: Phase2Trial[];
  revealDurationMs?: number;
  maxRatingMs?: number;
  itiMinMs?: number;
  itiMaxMs?: number;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function logEvent(
  ctx: TaskContext,
  type: string,
  payload?: Record<string, unknown>,
  blockId?: string,
) {
  postEvent(ctx.sessionId, ctx.token, { type, block_id: blockId, payload })
    .catch((err) => console.error(`[timeline] failed to log ${type}`, err));
}

function jitteredIti(minMs: number, maxMs: number): number {
  return Math.round(minMs + Math.random() * (maxMs - minMs));
}

function sliderHtml(stimulus: string): string {
  return `
    <div style="max-width:38rem;margin:0 auto;text-align:center;">
      ${stimulus}
      <p style="font-size:1rem;color:#475569;margin-bottom:1rem;">
        How much do you like this artwork?
      </p>
    </div>
  `;
}

function artworkImageHtml(trial: Artwork, size: "md" | "lg" = "lg"): string {
  const maxW = size === "lg" ? "360px" : "240px";
  if (trial.image_url) {
    return `<img src="${trial.image_url}"
                 alt="${trial.title}"
                 style="max-width:${maxW};max-height:280px;object-fit:contain;border-radius:4px;margin-bottom:0.75rem;">`;
  }
  // Fallback placeholder when image not yet downloaded
  return `
    <div style="width:${maxW};height:220px;background:#f1f5f9;border:1px solid #e2e8f0;
                border-radius:4px;display:flex;flex-direction:column;align-items:center;
                justify-content:center;margin:0 auto 0.75rem;color:#94a3b8;font-size:13px;">
      <div style="font-size:2rem;margin-bottom:0.5rem;">🖼</div>
      <div>${trial.title}</div>
      <div style="font-size:11px;margin-top:4px;">${trial.artist}, ${trial.year}</div>
    </div>
  `;
}

function agentRatingBarHtml(agentName: string, agentRating: number): string {
  const pct = agentRating;
  return `
    <div style="max-width:360px;margin:0 auto 1rem;background:#f8fafc;border:1px solid #e2e8f0;
                border-radius:8px;padding:12px 16px;">
      <div style="font-size:13px;color:#475569;margin-bottom:6px;">
        <strong>${agentName}</strong> rated this artwork:
        <span style="font-size:16px;font-weight:600;color:#1e293b;margin-left:8px;">${agentRating}</span>
        <span style="font-size:11px;color:#94a3b8;"> / 100</span>
      </div>
      <div style="height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;">
        <div style="width:${pct}%;height:100%;background:#475569;border-radius:4px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;margin-top:3px;">
        <span>0</span><span>100</span>
      </div>
    </div>
  `;
}

// ── Phase 1: Baseline Rating ──────────────────────────────────────────────────

function buildPhase1Trials(ctx: TaskContext, blockId: string, jsPsych: JsPsych) {
  const maxRatingMs = ctx.maxRatingMs ?? 8000;
  const itiMin = ctx.itiMinMs ?? 2000;
  const itiMax = ctx.itiMaxMs ?? 4000;

  return ctx.phase1Trials.flatMap((trial) => {
    let artworkOnsetMs: number | null = null;

    const ratingTrial = {
      type: HtmlSliderResponse,
      stimulus: sliderHtml(artworkImageHtml(trial)),
      labels: ["0", "100"],
      min: 0,
      max: 100,
      slider_start: 50,
      require_movement: true,
      button_label: "Submit",
      trial_duration: maxRatingMs,
      on_start: () => {
        artworkOnsetMs = performance.now();
        logEvent(ctx, "phase1_artwork_onset", { artwork_id: trial.artwork_id, trial_index: trial.trial_index }, blockId);
      },
      on_finish: async (data: { response: number; rt: number }) => {
        const rt = data.rt;
        logEvent(ctx, "phase1_rating_response", {
          artwork_id: trial.artwork_id,
          rating: data.response,
          rt_ms: rt,
          trial_index: trial.trial_index,
        }, blockId);
        await submitRating(ctx.sessionId, ctx.token, blockId, {
          artwork_id: trial.artwork_id,
          rating: data.response,
          artwork_onset_ms: artworkOnsetMs ?? undefined,
          rating_rt_ms: rt,
          trial_index: trial.trial_index,
        }).catch(console.error);
      },
    };

    const itiTrial = {
      type: HtmlKeyboardResponse,
      stimulus: `<div style="text-align:center;font-size:3rem;color:#64748b;">+</div>`,
      choices: "NO_KEYS" as const,
      trial_duration: jitteredIti(itiMin, itiMax),
    };

    return [ratingTrial, itiTrial];
  });
}

// ── Phase 2: Influence Task ───────────────────────────────────────────────────

function buildPhase2Trials(ctx: TaskContext, blockId: string, jsPsych: JsPsych) {
  const revealMs = ctx.revealDurationMs ?? 4000;
  const maxRatingMs = ctx.maxRatingMs ?? 8000;
  const itiMin = ctx.itiMinMs ?? 2000;
  const itiMax = ctx.itiMaxMs ?? 4000;

  return ctx.phase2Trials.flatMap((trial) => {
    let artworkOnsetMs: number | null = null;

    // Step 1: Reveal artwork + agent rating (fixed duration)
    const revealTrial = {
      type: HtmlKeyboardResponse,
      stimulus: `
        <div style="max-width:38rem;margin:0 auto;text-align:center;">
          ${artworkImageHtml(trial)}
          ${agentRatingBarHtml(trial.agent_condition, trial.agent_rating)}
        </div>
      `,
      choices: "NO_KEYS" as const,
      trial_duration: revealMs,
      on_start: () => {
        artworkOnsetMs = performance.now();
        logEvent(ctx, "phase2_reveal_onset", {
          artwork_id: trial.artwork_id,
          agent_condition: trial.agent_condition,
          agent_rating: trial.agent_rating,
          trial_index: trial.trial_index,
        }, blockId);
      },
      on_finish: () => {
        logEvent(ctx, "phase2_reveal_end", { artwork_id: trial.artwork_id }, blockId);
      },
    };

    // Step 2: Re-rating slider
    const ratingTrial = {
      type: HtmlSliderResponse,
      stimulus: sliderHtml(artworkImageHtml(trial, "md")),
      labels: ["0", "100"],
      min: 0,
      max: 100,
      slider_start: 50,
      require_movement: true,
      button_label: "Submit",
      trial_duration: maxRatingMs,
      on_finish: async (data: { response: number; rt: number }) => {
        logEvent(ctx, "phase2_rating_response", {
          artwork_id: trial.artwork_id,
          rating: data.response,
          agent_condition: trial.agent_condition,
          agent_rating: trial.agent_rating,
          rt_ms: data.rt,
          trial_index: trial.trial_index,
        }, blockId);
        await submitRating(ctx.sessionId, ctx.token, blockId, {
          artwork_id: trial.artwork_id,
          rating: data.response,
          agent_condition: trial.agent_condition,
          agent_rating: trial.agent_rating,
          artwork_onset_ms: artworkOnsetMs ?? undefined,
          rating_rt_ms: data.rt,
          trial_index: trial.trial_index,
        }).catch(console.error);
      },
    };

    // Step 3: ITI
    const itiTrial = {
      type: HtmlKeyboardResponse,
      stimulus: `<div style="text-align:center;font-size:3rem;color:#64748b;">+</div>`,
      choices: "NO_KEYS" as const,
      trial_duration: jitteredIti(itiMin, itiMax),
      on_start: () => logEvent(ctx, "iti_onset", { artwork_id: trial.artwork_id }, blockId),
    };

    return [revealTrial, ratingTrial, itiTrial];
  });
}

// ── Full Timeline Builder ─────────────────────────────────────────────────────

export async function buildTimeline(ctx: TaskContext, jsPsych: JsPsych) {
  // Create blocks up front so we have IDs for logging
  const phase1Block = await createBlock(ctx.sessionId, ctx.token, 1);
  const phase2Block = await createBlock(ctx.sessionId, ctx.token, 2);

  const phase1Trials = buildPhase1Trials(ctx, phase1Block.block_id, jsPsych);
  const phase2Trials = buildPhase2Trials(ctx, phase2Block.block_id, jsPsych);

  const scannerWait = {
    type: HtmlKeyboardResponse,
    stimulus: `
      <div style="text-align:center;color:#475569;">
        <div style="font-size:1.5rem;margin-bottom:1rem;">Waiting for scanner…</div>
        <div style="font-size:0.95rem;">The task will begin automatically.</div>
      </div>
    `,
    choices: ["5"],
    on_start: () => logEvent(ctx, "waiting_for_scanner_shown"),
    on_finish: () => logEvent(ctx, "first_tr_received"),
  };

  const phase1Instructions = {
    type: HtmlButtonResponse,
    stimulus: `
      <div style="max-width:34rem;margin:0 auto;text-align:left;">
        <h1 style="font-size:1.4rem;font-weight:600;margin-bottom:1rem;text-align:center;">
          Artwork Rating Task — Part 1
        </h1>
        <p style="margin-bottom:1rem;">
          You'll see a series of artworks. For each one, please rate how much you like it
          on a scale from <strong>0</strong> (not at all) to <strong>100</strong> (extremely).
        </p>
        <ul style="list-style:disc;padding-left:1.5rem;margin-bottom:1rem;">
          <li style="margin-bottom:0.4rem;">Move the slider to your rating and click <em>Submit</em>.</li>
          <li style="margin-bottom:0.4rem;">There are no right or wrong answers — go with your gut reaction.</li>
          <li>Work at your own pace.</li>
        </ul>
      </div>
    `,
    choices: ["Begin"],
    on_start: () => logEvent(ctx, "phase1_instructions_shown"),
    on_finish: () => {
      logEvent(ctx, "phase1_instructions_dismissed");
      logEvent(ctx, "phase1_start");
    },
  };

  const phase1End = {
    type: HtmlButtonResponse,
    stimulus: `
      <div style="max-width:32rem;margin:0 auto;text-align:center;">
        <h2 style="font-size:1.2rem;font-weight:600;margin-bottom:1rem;">Part 1 complete</h2>
        <p>Thank you. You've finished rating the artworks.</p>
        <p style="margin-top:0.75rem;color:#64748b;font-size:0.9rem;">
          Please inform the researcher that you have finished Part 1.
        </p>
      </div>
    `,
    choices: ["Continue"],
    on_start: () => logEvent(ctx, "phase1_end"),
  };

  const phase2Instructions = {
    type: HtmlButtonResponse,
    stimulus: `
      <div style="max-width:34rem;margin:0 auto;text-align:left;">
        <h1 style="font-size:1.4rem;font-weight:600;margin-bottom:1rem;text-align:center;">
          Artwork Rating Task — Part 2
        </h1>
        <p style="margin-bottom:1rem;">
          You'll see the same artworks again. This time, before you rate each one,
          you'll briefly see how someone else rated it.
        </p>
        <ul style="list-style:disc;padding-left:1.5rem;margin-bottom:1rem;">
          <li style="margin-bottom:0.4rem;">First, look at the other person's rating.</li>
          <li style="margin-bottom:0.4rem;">Then rate the artwork yourself on the same 0–100 scale.</li>
          <li>Your ratings can stay the same or change — it's up to you.</li>
        </ul>
      </div>
    `,
    choices: ["Begin"],
    on_start: () => logEvent(ctx, "phase2_instructions_shown"),
    on_finish: () => {
      logEvent(ctx, "phase2_instructions_dismissed");
      logEvent(ctx, "phase2_start");
    },
  };

  const endScreen = {
    type: HtmlButtonResponse,
    stimulus: `
      <div style="max-width:32rem;margin:0 auto;text-align:center;">
        <h2 style="font-size:1.25rem;font-weight:600;margin-bottom:1rem;">All done — thank you!</h2>
        <p>Your responses have been saved.</p>
      </div>
    `,
    choices: ["Finish"],
    on_start: () => logEvent(ctx, "task_end"),
    on_finish: () => logEvent(ctx, "timeline_complete"),
  };

  return [
    ...(ctx.mode === "scanner" ? [scannerWait] : []),
    phase1Instructions,
    ...phase1Trials,
    phase1End,
    phase2Instructions,
    ...phase2Trials,
    endScreen,
  ];
}
