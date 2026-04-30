type Props = {
  videoUrl: string | null;
};

export default function OnboardingPanel({ videoUrl }: Props) {
  if (!videoUrl) {
    return (
      <div className="panel">
        <div className="panel-header">Onboarding</div>
        <div className="panel-body text-sm text-slate-500">
          Your onboarding video is being prepared. Check back shortly.
        </div>
      </div>
    );
  }
  return (
    <div className="panel">
      <div className="panel-header">Welcome — your onboarding video</div>
      <div className="panel-body">
        <video
          data-testid="hg-video"
          src={videoUrl}
          controls
          autoPlay
          className="w-full rounded-md border border-slate-200"
        />
      </div>
    </div>
  );
}
