import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { saveReel } from "../api/client";

/** Regex to find a reel URL in a block of shared text. */
const URL_PATTERN =
  /https?:\/\/(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be|tiktok\.com|vm\.tiktok\.com)\S*/i;

function extractReelUrl(params: URLSearchParams): string | null {
  // Try the "url" param first (clean share)
  const directUrl = params.get("url");
  if (directUrl && URL_PATTERN.test(directUrl)) {
    return directUrl;
  }

  // Instagram & WhatsApp often put the URL inside "text"
  const text = params.get("text") ?? "";
  const match = text.match(URL_PATTERN);
  if (match) {
    // Strip tracking params like ?igsh=... but keep the path
    try {
      const parsed = new URL(match[0]);
      // Keep only the origin + pathname (drop query/hash)
      return `${parsed.origin}${parsed.pathname}`;
    } catch {
      return match[0];
    }
  }

  // Last resort: check "title" param
  const title = params.get("title") ?? "";
  const titleMatch = title.match(URL_PATTERN);
  if (titleMatch) return titleMatch[0];

  return null;
}

export default function Share() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"saving" | "done" | "error">("saving");
  const [error, setError] = useState("");
  const [reelUrl, setReelUrl] = useState("");

  useEffect(() => {
    const url = extractReelUrl(params);

    if (!url) {
      setStatus("error");
      setError("No reel URL found in shared content.");
      return;
    }

    setReelUrl(url);

    saveReel(url)
      .then((reel) => {
        setStatus("done");
        // Auto-navigate to the reel detail after a brief pause
        setTimeout(() => navigate(`/reels/${reel.id}`, { replace: true }), 1200);
      })
      .catch((err) => {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Failed to save reel");
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
      {status === "saving" && (
        <>
          <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
          <p className="mt-4 text-sm text-gray-600">Saving reel...</p>
          {reelUrl && (
            <p className="mt-1 max-w-xs truncate text-xs text-gray-400">
              {reelUrl}
            </p>
          )}
        </>
      )}

      {status === "done" && (
        <>
          <CheckCircle2 className="h-10 w-10 text-green-500" />
          <p className="mt-4 font-medium text-gray-800">Reel saved!</p>
          <p className="mt-1 text-sm text-gray-500">
            Processing will start automatically.
          </p>
        </>
      )}

      {status === "error" && (
        <>
          <AlertCircle className="h-10 w-10 text-red-500" />
          <p className="mt-4 font-medium text-gray-800">Couldn't save</p>
          <p className="mt-1 text-center text-sm text-red-600">{error}</p>
          <button
            onClick={() => navigate("/", { replace: true })}
            className="mt-6 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white"
          >
            Go Home
          </button>
        </>
      )}
    </div>
  );
}
