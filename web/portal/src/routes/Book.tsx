// /book?token=xxx — single-use interview-booking magic-link surface.
//
// 1. Resolve the token via GET /api/portal/interview/resolve to get the
//    candidate's role title + the deterministic 5×3 slot grid.
// 2. Render the grid grouped by day. Available slots are clickable,
//    unavailable ones are visibly disabled.
// 3. On click, POST /api/portal/interview/book with {token, slot_id}.
//    On 200: render a "booked" confirmation panel.
//    On 409 ("already booked"): render an explicit error.
import { useEffect, useState } from "react";
import {
  getBookingResolve,
  postBooking,
  type BookingResolveResponse,
  type InterviewSlot,
} from "../lib/api";

export default function Book() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") ?? "";
  const [data, setData] = useState<BookingResolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [bookedSlot, setBookedSlot] = useState<InterviewSlot | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing token in URL.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const body = await getBookingResolve(token);
        if (!cancelled) setData(body);
      } catch (err) {
        if (cancelled) return;
        const msg = (err as Error).message;
        setError(
          msg === "expired"
            ? "This booking link has expired. Please contact your recruiter for a fresh link."
            : `Could not load booking page (${msg}).`,
        );
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  async function pickSlot(slot: InterviewSlot) {
    if (submitting || !slot.available) return;
    setSubmitting(true);
    try {
      await postBooking(token, slot.slot_id);
      setBookedSlot(slot);
    } catch (err) {
      const msg = (err as Error).message;
      setError(
        msg === "already-booked"
          ? "Looks like you've already booked an interview with this link."
          : msg === "expired"
            ? "This booking link expired before you could use it."
            : `Booking failed (${msg}).`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel">
          <div className="panel-header">
            <span><span className="status-dot status-dot-error"/> Booking unavailable</span>
          </div>
          <div className="panel-body text-sm text-red-700">{error}</div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10 text-sm text-slate-500 flex items-center gap-2">
        <span className="spinner"/> Loading booking page…
      </div>
    );
  }

  if (bookedSlot) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel-elevated">
          <div className="panel-header">
            <span><span className="status-dot status-dot-active"/> Interview booked</span>
            <span className="chip-success">{bookedSlot.label}</span>
          </div>
          <div className="panel-body text-sm text-slate-700 space-y-2">
            <p>
              Thanks — your <strong>{data.role_title}</strong> interview is booked
              for <strong>{bookedSlot.label}</strong>. We'll email a Teams link
              shortly. You can close this tab.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Group slots by day for rendering.
  const byDay = new Map<string, InterviewSlot[]>();
  for (const s of data.slots) {
    const day = s.label.split(" · ")[0];
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(s);
  }

  return (
    <div className="max-w-3xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">Schedule your interview</div>
        <h1 className="hero-title">Pick a time that works for you</h1>
        <p className="hero-subtitle">
          {data.role_title} · single-use link, one selection per booking.
        </p>
      </div>
      <div className="space-y-4" data-testid="slot-grid">
        {Array.from(byDay.entries()).map(([day, slots]) => (
          <div key={day} className="panel">
            <div className="panel-header"><span>{day}</span></div>
            <div className="panel-body grid grid-cols-3 gap-2">
              {slots.map((s) => (
                <button
                  key={s.slot_id}
                  type="button"
                  disabled={!s.available || submitting}
                  onClick={() => pickSlot(s)}
                  className={
                    s.available
                      ? "btn-secondary"
                      : "btn-secondary opacity-40 cursor-not-allowed"
                  }
                >
                  {s.label.split(" · ")[1]}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
