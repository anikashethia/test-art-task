/**
 * Social Influence Task — jsPsych Timeline
 *
 * Two-phase structure:
 *   Phase 1 (baseline): 50 artwork ratings, no agent info shown.
 *   Phase 2 (influence): 50 artwork ratings, each preceded by agent's rating.
 *
 * Trial structure per Phase 2 trial:
 *   1. Artwork + agent rating reveal (4 s)
 *   2. Re-rating: participant rates on 0-100 slider (self-paced, <=8 s)
 *   3. ITI: fixation cross (2-4 s jittered)
 *
 * Phase 1 trials use the same slider, no reveal step.
 */

import type { JsPsych } from "jspsych";
import HtmlButtonResponse from "@jspsych/plugin-html-button-response";
import HtmlSliderResponse from "@jspsych/plugin-html-slider-response";
import HtmlKeyboardResponse from "@jspsych/plugin-html-keyboard-response";
import {
  createBlock,
  submitRating,
  postEvent,
  type Trial,
  type Mode,
} from "./api";

// ── Context ───────────────────────────────────────────────────────────────────

export type TaskContext = {
  sessionId: string;
  token: string;
  mode: Mode;
  trials: Trial[];
  revealDurationMs?: number;
  maxRatingMs?: number;
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


function sliderHtml(stimulus: string): string {
  return `
    <div style="max-width:50rem;margin:0 auto;text-align:center;">
      ${stimulus}
      <p style="font-size:1rem;color:#475569;margin-bottom:1rem;">
        How much do you like this artwork?
      </p>
    </div>
  `;
}

function artworkImageHtml(trial: Artwork, size: "md" | "lg" = "lg"): string {
  const maxW = size === "lg" ? "600px" : "480px";
  const maxH = size === "lg" ? "480px" : "360px";
  const placeholderH = size === "lg" ? "360px" : "280px";
  if (trial.image_url) {
    return `<img src="${trial.image_url}"
                 alt="${trial.title}"
                 style="max-width:${maxW};max-height:${maxH};object-fit:contain;border-radius:4px;margin:0 auto 0.75rem;display:block;">`;
  }
  return `
    <div style="width:${maxW};max-width:100%;height:${placeholderH};background:#f1f5f9;border:1px solid #e2e8f0;
                border-radius:4px;display:flex;flex-direction:column;align-items:center;
                justify-content:center;margin:0 auto 0.75rem;color:#94a3b8;font-size:13px;">
      <div style="font-size:2rem;margin-bottom:0.5rem;">🖼</div>
      <div>${trial.title}</div>
      <div style="font-size:11px;margin-top:4px;">${trial.artist}, ${trial.year}</div>
    </div>
  `;
}

function agentPairRevealHtml(agent1: string, agent2: string, avgRating: number): string {
  const avatar = `
    <div style="width:80px;height:80px;border-radius:50%;background:#e2e8f0;border:2px solid #cbd5e1;
                margin:0 auto 0.5rem;display:flex;align-items:center;justify-content:center;
                font-size:2.2rem;color:#94a3b8;">
      👤
    </div>
  `;
  return `
    <div style="display:flex;gap:3rem;justify-content:center;margin:1.25rem 0 1.5rem;">
      <div style="text-align:center;">
        ${avatar}
        <div style="font-size:0.95rem;font-weight:600;color:#334155;">${agent1}</div>
      </div>
      <div style="text-align:center;">
        ${avatar}
        <div style="font-size:0.95rem;font-weight:600;color:#334155;">${agent2}</div>
      </div>
    </div>
    <div style="text-align:center;font-size:1rem;color:#475569;">
      The average of <strong>${agent1}</strong> and <strong>${agent2}</strong>'s rating is
      <span style="font-size:2rem;font-weight:700;color:#1e293b;margin-left:0.3rem;">${avgRating}</span>
      <span style="font-size:0.85rem;color:#94a3b8;"> / 100</span>
    </div>
  `;
}

function addSliderValueDisplay() {
  const slider = document.querySelector('input[type="range"]') as HTMLInputElement | null;
  if (!slider) return;
  const display = document.createElement('div');
  display.style.cssText = 'text-align:center;font-size:2rem;font-weight:600;color:#1e293b;margin:0.5rem 0 0.25rem;min-height:2.5rem;';
  display.textContent = slider.value;
  slider.parentNode!.insertBefore(display, slider.nextSibling);
  slider.addEventListener('input', () => { display.textContent = slider.value; });
}

// ── Trials (rate → reveal → re-rate → ITI) ───────────────────────────────────

function buildTrials(ctx: TaskContext, blockId: string, _jsPsych: JsPsych) {
  const revealMs = ctx.revealDurationMs ?? 4000;
  const maxRatingMs = ctx.maxRatingMs ?? 10000;

  const missedStimulus = `
    <div style="position:fixed;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
      <div style="text-align:center;color:#94a3b8;">
        <p style="font-size:1.3rem;font-weight:500;">Out of time</p>
        <p style="font-size:0.9rem;margin-top:0.5rem;">Please try to respond before the timer runs out.</p>
      </div>
    </div>
  `;

  return ctx.trials.flatMap((trial) => {
    let artworkOnsetMs: number | null = null;
    let rerateOnsetMs: number | null = null;
    let initialMissed = false;
    let rerateMissed = false;

    const initialRatingTrial = {
      type: HtmlSliderResponse,
      stimulus: sliderHtml(artworkImageHtml(trial)),
      labels: ["0<br>Not at all", "100<br>Extremely"],
      min: 0,
      max: 100,
      slider_start: 50,
      require_movement: true,
      button_label: "Submit",
      trial_duration: maxRatingMs,
      on_load: addSliderValueDisplay,
      on_start: () => {
        artworkOnsetMs = performance.now();
        logEvent(ctx, "initial_rating_onset", { artwork_id: trial.artwork_id, trial_index: trial.trial_index }, blockId);
      },
      on_finish: async (data: { response: number | null; rt: number | null }) => {
        if (data.response === null) {
          initialMissed = true;
          logEvent(ctx, "initial_rating_missed", { artwork_id: trial.artwork_id, trial_index: trial.trial_index }, blockId);
          return;
        }
        initialMissed = false;
        logEvent(ctx, "initial_rating_response", {
          artwork_id: trial.artwork_id,
          rating: data.response,
          rt_ms: data.rt,
          trial_index: trial.trial_index,
        }, blockId);
        await submitRating(ctx.sessionId, ctx.token, blockId, {
          artwork_id: trial.artwork_id,
          rating: data.response,
          rating_type: "initial",
          artwork_onset_ms: artworkOnsetMs ?? undefined,
          rating_rt_ms: data.rt,
          trial_index: trial.trial_index,
        }).catch(console.error);
      },
    };

    const revealTrial = {
      type: HtmlKeyboardResponse,
      stimulus: `
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
          <div style="max-width:50rem;width:100%;text-align:center;padding:0 1rem;">
            ${artworkImageHtml(trial)}
            ${agentPairRevealHtml(trial.agent1, trial.agent2, trial.avg_rating)}
          </div>
        </div>
      `,
      choices: "NO_KEYS" as const,
      trial_duration: revealMs,
      on_start: () => {
        logEvent(ctx, "reveal_onset", {
          artwork_id: trial.artwork_id,
          pair_condition: trial.pair_condition,
          agent1: trial.agent1,
          agent2: trial.agent2,
          avg_rating: trial.avg_rating,
          trial_index: trial.trial_index,
        }, blockId);
      },
      on_finish: () => {
        logEvent(ctx, "reveal_end", { artwork_id: trial.artwork_id }, blockId);
      },
    };

    const reratingTrial = {
      type: HtmlSliderResponse,
      stimulus: sliderHtml(artworkImageHtml(trial, "md")),
      labels: ["0<br>Not at all", "100<br>Extremely"],
      min: 0,
      max: 100,
      slider_start: 50,
      require_movement: true,
      button_label: "Submit",
      trial_duration: maxRatingMs,
      on_load: addSliderValueDisplay,
      on_start: () => { rerateOnsetMs = performance.now(); },
      on_finish: async (data: { response: number | null; rt: number | null }) => {
        if (data.response === null) {
          rerateMissed = true;
          logEvent(ctx, "rerate_missed", { artwork_id: trial.artwork_id, trial_index: trial.trial_index }, blockId);
          return;
        }
        rerateMissed = false;
        logEvent(ctx, "rerate_response", {
          artwork_id: trial.artwork_id,
          rating: data.response,
          pair_condition: trial.pair_condition,
          agent1: trial.agent1,
          agent2: trial.agent2,
          avg_rating: trial.avg_rating,
          rt_ms: data.rt,
          trial_index: trial.trial_index,
        }, blockId);
        await submitRating(ctx.sessionId, ctx.token, blockId, {
          artwork_id: trial.artwork_id,
          rating: data.response,
          rating_type: "rerate",
          pair_condition: trial.pair_condition,
          agent1_condition: trial.agent1,
          agent2_condition: trial.agent2,
          agent1_rating: trial.agent1_rating,
          agent2_rating: trial.agent2_rating,
          avg_rating: trial.avg_rating,
          artwork_onset_ms: rerateOnsetMs ?? undefined,
          rating_rt_ms: data.rt,
          trial_index: trial.trial_index,
        }).catch(console.error);
      },
    };

    const blankScreen = {
      type: HtmlKeyboardResponse,
      stimulus: "",
      choices: "NO_KEYS" as const,
      trial_duration: 500,
    };

    return [
      initialRatingTrial,
      { timeline: [{ type: HtmlKeyboardResponse, stimulus: missedStimulus, choices: "NO_KEYS" as const, trial_duration: 2000 }], conditional_function: () => initialMissed },
      revealTrial,
      reratingTrial,
      { timeline: [{ type: HtmlKeyboardResponse, stimulus: missedStimulus, choices: "NO_KEYS" as const, trial_duration: 2000 }], conditional_function: () => rerateMissed },
      blankScreen,
    ];
  });
}

// ── Full Timeline Builder ─────────────────────────────────────────────────────

export async function buildTimeline(ctx: TaskContext, _jsPsych: JsPsych) {
  const block = await createBlock(ctx.sessionId, ctx.token, 1);
  const trials = buildTrials(ctx, block.block_id, _jsPsych);

  const instructions = {
    type: HtmlButtonResponse,
    stimulus: `
      <div style="max-width:34rem;margin:0 auto;text-align:left;">
        <h1 style="font-size:1.4rem;font-weight:600;margin-bottom:1rem;text-align:center;">
          Artwork Rating Task
        </h1>
        <p style="margin-bottom:1rem;">
          You'll see a series of artworks. For each one:
        </p>
        <ol style="padding-left:1.5rem;margin-bottom:1rem;">
          <li style="margin-bottom:0.6rem;">
            <strong>Rate</strong> how much you like it on a scale from
            <strong>0</strong> (not at all) to <strong>100</strong> (extremely).
          </li>
          <li style="margin-bottom:0.6rem;">
            You'll briefly see <strong>how someone else rated it</strong>.
          </li>
          <li style="margin-bottom:0.6rem;">
            <strong>Rate it again</strong> — your rating can stay the same or change.
          </li>
        </ol>
        <p style="color:#64748b;font-size:0.9rem;">
          There are no right or wrong answers — go with your honest reaction.
        </p>
      </div>
    `,
    choices: ["Begin"],
    on_start: () => logEvent(ctx, "instructions_shown"),
    on_finish: () => {
      logEvent(ctx, "instructions_dismissed");
      logEvent(ctx, "task_start");
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

  return [instructions, ...trials, endScreen];
}
