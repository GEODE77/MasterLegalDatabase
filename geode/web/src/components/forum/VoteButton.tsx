"use client";

import { useEffect, useState, type ReactElement } from "react";

type VoteButtonProps = {
  count: number;
  label: string;
  onVote: (delta: number) => Promise<void>;
};

export function VoteButton({ count, label, onVote }: VoteButtonProps): ReactElement {
  const [displayedCount, setDisplayedCount] = useState(count);
  const [isPressed, setIsPressed] = useState(false);
  const [direction, setDirection] = useState<"down" | "up" | null>(null);

  useEffect(() => {
    setDisplayedCount(count);
  }, [count]);

  async function vote(delta: number): Promise<void> {
    setIsPressed(true);
    setDirection(delta > 0 ? "up" : "down");
    setDisplayedCount((value) => value + Math.sign(delta));
    await onVote(delta);
    window.setTimeout(() => {
      setIsPressed(false);
      setDirection(null);
    }, 240);
  }

  return (
    <div
      className={`vote-stack${isPressed ? " is-pressed" : ""}${direction ? ` is-${direction}` : ""}`}
      aria-label={label}
    >
      <button aria-label="Upvote" onClick={() => void vote(1)} type="button">
        Useful
      </button>
      <span>{displayedCount}</span>
      <button aria-label="Downvote" onClick={() => void vote(-1)} type="button">
        Not useful
      </button>
    </div>
  );
}
