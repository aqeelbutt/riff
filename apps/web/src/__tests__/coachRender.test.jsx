import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Coach } from "@/components/ui/Coach";
import { coachKey } from "@/lib/coach";
import { lyricSyncSteps } from "@/features/player/lyricSyncCoach";

// The anchor nodes go straight on document.body, which RTL's cleanup() doesn't own — clear them by hand or
// they leak into the next test and every step resolves whether the test staged it or not.
afterEach(() => {
  cleanup();
  document.querySelectorAll("[data-coach]").forEach((el) => el.closest("div[data-coach-host]")?.remove() ?? el.remove());
  localStorage.clear();
});

// jsdom has no layout, so every rect is 0×0 — fine here: we're testing which step shows and what closing does,
// not pixel placement (that's covered purely in coach.test.js).
const page = (ids) => {
  const host = document.createElement("div");
  host.setAttribute("data-coach-host", "");
  ids.forEach((id) => { const el = document.createElement("div"); el.setAttribute("data-coach", id); host.appendChild(el); });
  document.body.appendChild(host);
  return host;
};
const STEPS = [
  { anchor: "sync-button", title: "One", body: ["a"] },
  { anchor: "versions", title: "Two", body: ["b"] },
  { anchor: "lyrics", title: "Three", body: ["c"] },
];

describe("Coach", () => {
  it("opens on the first step and counts only the steps it can anchor", () => {
    page(["sync-button", "versions", "lyrics"]);
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={() => {}} />);
    expect(screen.getByRole("heading", { name: "One" })).toBeInTheDocument();
    expect(screen.getByText(/1 of 3/)).toBeInTheDocument();
  });

  it("drops steps whose target isn't on the page rather than pointing at nothing", () => {
    page(["sync-button", "lyrics"]); // no "versions" — e.g. a song with no takes yet
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={() => {}} />);
    expect(screen.getByText(/1 of 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Three" })).toBeInTheDocument();
  });

  it("closes immediately when nothing on the page can be pointed at", () => {
    page([]);
    const onClose = vi.fn();
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={onClose} />);
    expect(onClose).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("walks forward and back, and only offers Back past the first step", () => {
    page(["sync-button", "versions", "lyrics"]);
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={() => {}} />);
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Two" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "One" })).toBeInTheDocument();
  });

  it("marks itself seen on finish so it never runs unprompted twice", () => {
    page(["sync-button", "versions", "lyrics"]);
    const onClose = vi.fn();
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(onClose).toHaveBeenCalled();
    expect(localStorage.getItem(coachKey("lyric-sync"))).toBe("1");
  });

  it("marks seen on Skip too — dismissing is an answer", () => {
    page(["sync-button", "versions", "lyrics"]);
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(localStorage.getItem(coachKey("lyric-sync"))).toBe("1");
  });

  it("closes on Escape", () => {
    page(["sync-button", "versions", "lyrics"]);
    const onClose = vi.fn();
    render(<Coach name="lyric-sync" steps={STEPS} open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("renders nothing at all when closed", () => {
    page(["sync-button"]);
    render(<Coach name="lyric-sync" steps={STEPS} open={false} onClose={() => {}} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("lyricSyncSteps", () => {
  it("speaks the page's own word for a piece of audio", () => {
    expect(lyricSyncSteps({ unit: "version" })[1].title).toBe("Every version gets its own timing");
    expect(lyricSyncSteps({ unit: "take" })[1].title).toBe("Every take gets its own timing");
  });

  it("points the approximate step at the real note when one is showing, else at the lyrics panel", () => {
    expect(lyricSyncSteps({ hasApprox: true }).at(-1).anchor).toBe("lyric-approx");
    expect(lyricSyncSteps({ hasApprox: false }).at(-1).anchor).toBe("lyrics");
  });
});
