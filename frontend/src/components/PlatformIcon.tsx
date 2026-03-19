const colors: Record<string, string> = {
  instagram: "bg-pink-100 text-pink-600",
  youtube: "bg-red-100 text-red-600",
  tiktok: "bg-gray-900 text-white",
};

const labels: Record<string, string> = {
  instagram: "IG",
  youtube: "YT",
  tiktok: "TT",
};

export default function PlatformIcon({ platform }: { platform: string | null }) {
  const p = platform ?? "unknown";
  const color = colors[p] ?? "bg-gray-100 text-gray-600";
  const label = labels[p] ?? "?";

  return (
    <span
      className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ${color}`}
    >
      {label}
    </span>
  );
}
