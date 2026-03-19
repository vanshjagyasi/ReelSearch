import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Film } from "lucide-react";
import type { ReelResponse } from "../types";
import StatusBadge from "./StatusBadge";
import PlatformIcon from "./PlatformIcon";

export default function ReelCard({ reel }: { reel: ReelResponse }) {
  const [thumbFailed, setThumbFailed] = useState(false);
  const handleError = useCallback(() => setThumbFailed(true), []);

  return (
    <Link
      to={`/reels/${reel.id}`}
      className="flex gap-3 rounded-xl border border-gray-200 bg-white p-3 transition hover:border-indigo-200 hover:shadow-sm"
    >
      {/* Thumbnail */}
      <div className="h-20 w-16 flex-shrink-0 overflow-hidden rounded-lg bg-gray-100">
        {!thumbFailed ? (
          <img
            src={`/api/reels/${reel.id}/thumbnail`}
            alt=""
            className="h-full w-full object-cover"
            onError={handleError}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-300">
            <Film size={20} />
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <PlatformIcon platform={reel.platform} />
            <span className="text-sm font-medium text-gray-700 truncate max-w-[180px] md:max-w-none">
              {reel.url.replace(/^https?:\/\//, "").split("/").slice(0, 2).join("/")}
            </span>
          </div>
          <StatusBadge status={reel.status} />
        </div>
        <div className="mt-1 flex items-center justify-between text-xs text-gray-400">
          <span>{new Date(reel.created_at).toLocaleDateString()}</span>
          <a
            href={reel.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-indigo-500 hover:text-indigo-600"
          >
            Open <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </Link>
  );
}
