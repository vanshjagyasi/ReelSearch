import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  Trash2,
} from "lucide-react";
import { getReel, deleteReel, getReelStatus } from "../api/client";
import type { ReelDetail as ReelDetailType, ReelStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import PlatformIcon from "../components/PlatformIcon";

export default function ReelDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [reel, setReel] = useState<ReelDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getReel(id)
      .then(setReel)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load reel"),
      )
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll status while processing
  useEffect(() => {
    if (!id || !reel || reel.status === "ready" || reel.status === "failed")
      return;

    const interval = setInterval(async () => {
      try {
        const status: ReelStatus = await getReelStatus(id);
        if (status.status !== reel.status) {
          load();
        }
      } catch {
        /* ignore polling errors */
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [id, reel, load]);

  async function handleDelete() {
    if (!id || !confirm("Delete this reel?")) return;
    setDeleting(true);
    try {
      await deleteReel(id);
      navigate("/");
    } catch {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (error || !reel) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
        {error || "Reel not found"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100"
        >
          <ArrowLeft size={18} />
        </button>
        <PlatformIcon platform={reel.platform} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={reel.status} />
            {reel.creator && (
              <span className="text-sm text-gray-500">@{reel.creator}</span>
            )}
          </div>
        </div>
        <a
          href={reel.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-indigo-500"
        >
          <ExternalLink size={16} />
        </a>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:bg-red-50 hover:text-red-500"
        >
          <Trash2 size={16} />
        </button>
      </div>

      {/* Processing indicator */}
      {(reel.status === "pending" || reel.status === "processing") && (
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
          <Loader2 size={16} className="animate-spin" />
          This reel is being processed. The page will update automatically.
        </div>
      )}

      {/* Summary */}
      {reel.ai_summary && (
        <Section title="AI Summary">
          <p className="text-sm leading-relaxed text-gray-700">
            {reel.ai_summary}
          </p>
        </Section>
      )}

      {/* Tags */}
      {reel.ai_tags && reel.ai_tags.length > 0 && (
        <Section title="Tags">
          <div className="flex flex-wrap gap-1.5">
            {reel.ai_tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600"
              >
                {tag}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Content type & mood */}
      {(reel.content_type || reel.mood) && (
        <div className="grid grid-cols-2 gap-3">
          {reel.content_type && (
            <Section title="Content Type">
              <span className="text-sm capitalize text-gray-700">
                {reel.content_type}
              </span>
            </Section>
          )}
          {reel.mood && (
            <Section title="Mood">
              <span className="text-sm capitalize text-gray-700">
                {reel.mood}
              </span>
            </Section>
          )}
        </div>
      )}

      {/* Caption */}
      {reel.caption && (
        <Section title="Caption">
          <p className="whitespace-pre-wrap text-sm text-gray-700">
            {reel.caption}
          </p>
        </Section>
      )}

      {/* Transcript */}
      {reel.transcript && (
        <Section title="Transcript">
          <p className="whitespace-pre-wrap text-sm text-gray-700">
            {reel.transcript}
          </p>
        </Section>
      )}

      {/* Frame Description */}
      {reel.frame_description && (
        <Section title="Visual Description">
          <p className="whitespace-pre-wrap text-sm text-gray-700">
            {reel.frame_description}
          </p>
        </Section>
      )}

      {/* Metadata */}
      <div className="border-t border-gray-100 pt-4 text-xs text-gray-400">
        <p>Saved {new Date(reel.created_at).toLocaleString()}</p>
        {reel.updated_at && (
          <p>Updated {new Date(reel.updated_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        {title}
      </h3>
      {children}
    </div>
  );
}
