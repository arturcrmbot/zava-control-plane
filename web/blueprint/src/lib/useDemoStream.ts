import { useEffect, useState } from "react";

const STATUS_URL = "/api/blueprint/_demo_stream/status";
const START_URL = "/api/blueprint/_demo_stream/start";
const STOP_URL = "/api/blueprint/_demo_stream/stop";

/**
 * Manage the always-on demo trickle: a single endpoint pair on the FastAPI
 * side that runs an indefinite background task. The page is alive as long
 * as the trickle is running.
 */
export function useDemoStream() {
  const [running, setRunning] = useState<boolean | null>(null);
  const [pending, setPending] = useState(false);

  // Initial status check.
  useEffect(() => {
    let cancelled = false;
    fetch(STATUS_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((j) => {
        if (!cancelled) setRunning(!!j.running);
      })
      .catch(() => {
        if (!cancelled) setRunning(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function start() {
    setPending(true);
    try {
      await fetch(START_URL, { method: "POST" });
      setRunning(true);
    } finally {
      setPending(false);
    }
  }

  async function stop() {
    setPending(true);
    try {
      await fetch(STOP_URL, { method: "POST" });
      setRunning(false);
    } finally {
      setPending(false);
    }
  }

  return { running, pending, start, stop };
}
