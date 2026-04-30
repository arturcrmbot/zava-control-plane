// /screen?token=xxx — placeholder route.
// The voice-real subagent (Stream 2) fills this slot with the real <ScreenCall/>
// accelerator component. Until then, the mount div is the only contract.
export default function Screen() {
  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center bg-slate-100">
      <div
        id="screen-call-mount"
        data-testid="screen-call-mount"
        className="w-full max-w-3xl aspect-video rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-sm text-slate-500"
      >
        Screening call surface — Stream 2 voice-real subagent fills this slot.
      </div>
    </div>
  );
}
