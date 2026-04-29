/**
 * Entry point — routes to PilotApp (Prolific) or dev App based on ?mode=pilot.
 *
 * Prolific study URL:
 *   https://yourstudy.com/?mode=pilot&PROLIFIC_PID={{%PROLIFIC_PID%}}&identities=Alex,Sam,Casey,Jordan
 *
 * Dev URL:
 *   http://localhost:5174/
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import PilotApp from "./PilotApp";

const mode = new URLSearchParams(window.location.search).get("mode");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {mode === "pilot" ? <PilotApp /> : <App />}
  </StrictMode>,
);
