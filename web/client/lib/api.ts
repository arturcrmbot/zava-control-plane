export const REPLAY_BLOCKED_EVENT = "zava:replay-blocked" as const;

export interface ReplayBlockedDetail {
  message: string;
}

const DEFAULT_REPLAY_MESSAGE = "This is a replay — actions are observed, not made.";

function getMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  if (input instanceof Request) return input.method.toUpperCase();
  return "GET";
}

function dispatchReplayBlocked(detail: ReplayBlockedDetail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<ReplayBlockedDetail>(REPLAY_BLOCKED_EVENT, { detail }));
}

export async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, init);
  if (getMethod(input, init) === "GET" || response.status !== 403) return response;

  try {
    const body = await response.clone().json() as { error?: string; message?: string };
    if (body?.error !== "replay") return response;

    // Fire the friendly toast via global event, but return the original
    // 403 so callers' `!r.ok` paths run normally and any optimistic UI
    // gets reverted. Previously we swapped this to a 204 ("no-op") which
    // caused callers like HITLCard to treat the click as a SUCCESS and
    // leave the optimistic "Approved" flip in place — visitors then saw
    // a replay toast yet a fully-resolved card.
    dispatchReplayBlocked({ message: body.message ?? DEFAULT_REPLAY_MESSAGE });
    return response;
  } catch {
    return response;
  }
}
