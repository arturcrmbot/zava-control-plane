type Props = {
  videoUrl: string | null;
  candidateName?: string;
  roleLabel?: string;
};

const DAY1_CHECKLIST = [
  { icon: "💻", text: "Laptop, badges, and ServiceNow tickets pre-provisioned" },
  { icon: "📅", text: "Day 1 calendar — meet the team, 30/60/90 plan, manager 1:1" },
  { icon: "📚", text: "Role-specific onboarding playbook in your inbox" },
  { icon: "🤝", text: "Onboarding buddy assigned — they'll DM you on day 1" },
];

export default function OnboardingPanel({ videoUrl, candidateName, roleLabel }: Props) {
  const firstName = candidateName?.split(" ")[0] ?? "there";

  if (!videoUrl) {
    return (
      <div className="panel-elevated">
        <div className="panel-header">
          <span><span className="status-dot status-dot-pending"/> Welcome video being prepared</span>
        </div>
        <div className="panel-body space-y-3 text-sm text-slate-700">
          <p>
            Hi {firstName} — your personal welcome video is rendering right now
            (Azure Speech avatar synthesis takes ~1–2 minutes for the first run).
          </p>
          <p className="text-xs text-slate-500">This page auto-refreshes every 8 seconds.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="panel-elevated">
        <div className="panel-header">
          <span><span className="status-dot status-dot-active"/> Welcome to the team, {firstName} 🎉</span>
          {roleLabel && <span className="chip-info">{roleLabel}</span>}
        </div>
        <div className="panel-body space-y-4">
          <p className="text-sm text-slate-700">
            Watch your personal day-1 welcome below. After the video, scroll
            down for your day-1 checklist.
          </p>
          <div className="video-frame">
            <video
              data-testid="hg-video"
              src={videoUrl}
              controls
              autoPlay
              className="w-full aspect-video block"
            />
          </div>
          <p className="text-xs text-slate-500">
            Powered by Azure AI Speech batch avatar synthesis · cached after first render
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">Day 1 checklist</div>
        <div className="panel-body grid grid-cols-1 sm:grid-cols-2 gap-3">
          {DAY1_CHECKLIST.map((item, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 bg-slate-50/60">
              <span className="text-xl">{item.icon}</span>
              <span className="text-sm text-slate-700">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
