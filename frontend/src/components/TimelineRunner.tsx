/**
 * TimelineRunner — mounts jsPsych and runs the influence task timeline.
 * Mirrors the social connection task's TimelineRunner.tsx.
 */

import { useEffect, useRef } from "react";
import { initJsPsych } from "jspsych";
import "jspsych/css/jspsych.css";
import { buildTimeline } from "../timeline";
import type { TaskContext } from "../timeline";
import { postTrigger } from "../api";

type Props = {
  ctx: TaskContext;
  onComplete: () => void;
};

export default function TimelineRunner({ ctx, onComplete }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || startedRef.current) return;
    startedRef.current = true;

    const jsPsych = initJsPsych({
      display_element: containerRef.current,
      on_finish: () => onComplete(),
    });

    buildTimeline(ctx, jsPsych).then((timeline) => {
      jsPsych.run(timeline);
    });
  }, [ctx, onComplete]);

  // Scanner mode: log every '5' keypress as a TR
  useEffect(() => {
    if (ctx.mode !== "scanner") return;
    let trNumber = 0;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "5") return;
      const n = trNumber++;
      postTrigger(ctx.sessionId, ctx.token, { tr_number: n }).catch((err) =>
        console.error(`[tr] failed to log trigger ${n}`, err),
      );
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [ctx.mode, ctx.sessionId, ctx.token]);

  return <div ref={containerRef} className="min-h-screen" />;
}
