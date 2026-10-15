"use client";

import { useState } from "react";

/**
 * Waitlist for SMS alerts. It does not send SMS.
 *
 * There is no provider wired up, so the only honest version of this form is
 * one that says so before you type -- not after, and not in small print. A
 * form that looks like it subscribes you to a safety alert and silently does
 * nothing is worse than no form, because the person walks away believing they
 * will be told.
 *
 * What it does do is record interest in the same database as the evidence, so
 * the day a provider exists there is a list to migrate rather than a guess.
 */

type State =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "done"; already: boolean }
  | { kind: "error"; message: string };

export function AlertWaitlist({ projectId }: { projectId: string }) {
  const [phone, setPhone] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState({ kind: "sending" });
    try {
      const res = await fetch(`/api/projects/${projectId}/alert-waitlist`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setState({
          kind: "error",
          message: body?.message ?? "Could not record that just now.",
        });
        return;
      }
      setState({ kind: "done", already: Boolean(body?.already_registered) });
    } catch {
      setState({ kind: "error", message: "Could not reach the server." });
    }
  }

  return (
    <div className="waitlist">
      <p className="waitlist-tag mono">Waitlist &mdash; Africa&rsquo;s Talking, not live yet</p>
      <h3 className="waitlist-title">Be told when this site diverges.</h3>
      <p className="waitlist-body">
        An alert fires when a site sits below its approved trajectory for two
        consecutive months. Delivery will run on Africa&rsquo;s Talking, which is
        not connected yet &mdash; joining records your interest and nothing is
        sent. We keep the number and the project: no name, no email.
      </p>

      {state.kind === "done" ? (
        <p className="waitlist-ok">
          {state.already
            ? "That number is already on the list for this site."
            : "Recorded. Nothing will reach you until Africa\u2019s Talking is connected."}
        </p>
      ) : (
        <form className="waitlist-form" onSubmit={submit}>
          <label className="waitlist-label mono" htmlFor="wl-phone">
            Phone number
          </label>
          <div className="waitlist-row">
            <input
              id="wl-phone"
              className="waitlist-input mono"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="+254712345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
            <button
              type="submit"
              className="waitlist-btn"
              disabled={state.kind === "sending" || phone.trim().length < 8}
            >
              {state.kind === "sending" ? "Joining…" : "Join the waitlist"}
            </button>
          </div>
          {state.kind === "error" && (
            <p className="waitlist-err">{state.message}</p>
          )}
        </form>
      )}
    </div>
  );
}
