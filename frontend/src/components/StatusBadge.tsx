import { Loader2, CheckCircle2, AlertCircle, Clock } from "lucide-react";

const config: Record<string, { bg: string; text: string; icon: typeof Clock }> = {
  pending: { bg: "bg-yellow-50", text: "text-yellow-700", icon: Clock },
  processing: { bg: "bg-blue-50", text: "text-blue-700", icon: Loader2 },
  ready: { bg: "bg-green-50", text: "text-green-700", icon: CheckCircle2 },
  failed: { bg: "bg-red-50", text: "text-red-700", icon: AlertCircle },
};

export default function StatusBadge({ status }: { status: string }) {
  const c = config[status] ?? config["pending"]!;
  const Icon = c.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}
    >
      <Icon size={12} className={status === "processing" ? "animate-spin" : ""} />
      {status}
    </span>
  );
}
