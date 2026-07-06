"use client";

import { useEffect, useState, type ReactElement } from "react";

const EXAMPLE_QUESTIONS = [
  "What are the regulations for worker compensation?",
  "Which Colorado rules govern water discharge for manufacturing?",
  "What OSHA obligations apply to ceramic dust exposure?",
  "Which air quality regulations should leadership review first?",
];

type AnimatedPlaceholderProps = {
  hidden: boolean;
};

export function AnimatedPlaceholder({ hidden }: AnimatedPlaceholderProps): ReactElement {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % EXAMPLE_QUESTIONS.length);
    }, 3200);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  return (
    <span className={hidden ? "query-placeholder is-hidden" : "query-placeholder"}>
      {EXAMPLE_QUESTIONS[index]}
    </span>
  );
}
