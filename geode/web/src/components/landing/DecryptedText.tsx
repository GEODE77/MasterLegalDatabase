"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactElement } from "react";

type DecryptedTextProps = {
  readonly text: string;
};

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>/{}[]";

export function DecryptedText({ text }: DecryptedTextProps): ReactElement {
  const [frame, setFrame] = useState(0);
  const characters = useMemo(() => text.split(""), [text]);

  useEffect(() => {
    let current = 0;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (reducedMotion.matches) {
      setFrame(characters.length + 6);
      return undefined;
    }

    const interval = window.setInterval(() => {
      current += 1;
      setFrame(current);

      if (current > characters.length + 6) {
        window.clearInterval(interval);
      }
    }, 36);

    return () => window.clearInterval(interval);
  }, [characters.length]);

  return (
    <span aria-label={text} className="decrypted-text">
      {characters.map((character, index) => {
        const revealed = frame > index + 4 || character === " ";
        const glyph = GLYPHS[(index * 7 + frame * 3) % GLYPHS.length];

        return (
          <span
            aria-hidden="true"
            className={revealed ? "decrypted-letter is-revealed" : "decrypted-letter"}
            key={`${character}-${index}`}
          >
            {revealed ? character : glyph}
          </span>
        );
      })}
    </span>
  );
}
