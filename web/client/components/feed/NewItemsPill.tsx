import { ArrowUp } from "lucide-react";

export default function NewItemsPill({
  count, onPullIn,
}: {
  count: number;
  onPullIn: () => void;
}) {
  if (count <= 0) return null;
  return (
    <div className="flex justify-center sticky top-14 z-10 -mt-1 mb-2 pointer-events-none">
      <button
        type="button"
        onClick={onPullIn}
        className="pointer-events-auto text-xs px-3 py-1.5 rounded-full bg-blue-600 text-white shadow font-medium flex items-center gap-1 hover:bg-blue-700"
      >
        <ArrowUp size={12} />
        {count} new
      </button>
    </div>
  );
}
