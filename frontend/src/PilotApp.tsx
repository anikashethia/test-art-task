/**
 * PilotApp.tsx — Prolific participant-facing orchestrator.
 *
 * Reads PROLIFIC_PID from URL, creates a session, runs the full timeline,
 * then redirects to Prolific completion URL.
 *
 * Rendered when ?mode=pilot is in the URL (see main.tsx).
 *
 * Note: agent_identities are passed from the social connection task rotation
 * via URL params (e.g. ?identities=Alex,Sam,Casey,Jordan) so Phase 2 trial
 * labels match the agents the participant already interacted with.
 */

import { useState, useEffect, useCallback } from "react";
import TimelineRunner from "./components/TimelineRunner";
import { createSession, completeSession } from "./api";
import type { TaskContext } from "./timeline";

type Phase =
  | { name: "loading" }
  | { name: "error"; message: string }
  | { name: "running"; ctx: TaskContext }
  | { name: "complete"; prolificUrl: string };

function getProlificPid(): string {
  const p = new URLSearchParams(window.location.search);
  return p.get("PROLIFIC_PID") ?? p.get("prolific_pid") ?? "PILOT_ANON";
}

export default function PilotApp() {
  const [phase, setPhase] = useState<Phase>({ name: "loading" });

  const init = useCallback(async () => {
    try {
      const pid = getProlificPid();

      const s = await createSession({
        participant_id: pid,
        mode: "pilot",
      });

      setPhase({
        name: "running",
        ctx: {
          sessionId: s.session_id,
          token: s.session_token,
          mode: "pilot",
          phase1Trials: s.phase1_trials,
          phase2Trials: s.phase2_trials,
        },
      });
    } catch (e) {
      setPhase({
        name: "error",
        message: e instanceof Error ? e.message : "Setup failed",
      });
    }
  }, []);

  useEffect(() => { init(); }, [init]);

  const handleComplete = useCallback(async () => {
    if (phase.name !== "running") return;
    try {
      const { prolific_completion_url } = await completeSession(
        phase.ctx.sessionId,
        phase.ctx.token,
      );
      setPhase({ name: "complete", prolificUrl: prolific_completion_url });
    } catch {
      setPhase({ name: "complete", prolificUrl: "" });
    }
  }, [phase]);

  if (phase.name === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500 text-sm">Setting up your session…</p>
      </div>
    );
  }

  if (phase.name === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="max-w-md text-center p-8">
          <p className="text-red-600 font-medium mb-2">Something went wrong</p>
          <p className="text-slate-500 text-sm mb-4">{phase.message}</p>
          <p className="text-slate-400 text-sm">
            Please return to Prolific and contact the researcher.
          </p>
        </div>
      </div>
    );
  }

  if (phase.name === "running") {
    return <TimelineRunner ctx={phase.ctx} onComplete={handleComplete} />;
  }

  // Complete
  if (phase.prolificUrl) {
    setTimeout(() => { window.location.href = phase.prolificUrl; }, 3000);
  }
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="max-w-md text-center p-8 bg-white rounded-lg shadow">
        <h2 className="text-xl font-semibold text-slate-900 mb-3">
          Thank you — all done!
        </h2>
        <p className="text-slate-600 mb-4">Your responses have been saved.</p>
        {phase.prolificUrl ? (
          <p className="text-slate-500 text-sm">Redirecting you back to Prolific…</p>
        ) : (
          <p className="text-slate-500 text-sm">You may close this tab.</p>
        )}
      </div>
    </div>
  );
}
