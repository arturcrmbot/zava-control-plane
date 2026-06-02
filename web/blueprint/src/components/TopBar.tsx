import { useEffect, useRef, useState } from "react";
import { BOOKING_URL } from "../lib/links";

// Thin sticky bar that appears once the reader scrolls past the Opening
// section. Restrained on purpose: no logo, no shadow, just the essay
// headline on the left and a single CTA on the right. Hidden on initial
// paint so the headline lands cleanly.
export function TopBar() {
  const [visible, setVisible] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const sentinel = document.querySelector(
      ".opening",
    ) as HTMLElement | null;
    if (!sentinel) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        setVisible(!entry.isIntersecting);
      },
      { threshold: 0, rootMargin: "-1px 0px 0px 0px" },
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={sentinelRef}
      className={`topbar ${visible ? "topbar--visible" : ""}`}
      role="navigation"
      aria-label="Essay navigation"
      aria-hidden={!visible}
    >
      <div className="topbar__inner">
        <span className="topbar__caption">
          Why your agentic strategy isn&apos;t moving the needle.
        </span>
        <a
          className="topbar__cta"
          href={BOOKING_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Let&apos;s talk →
        </a>
      </div>
    </div>
  );
}
