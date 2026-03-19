import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { listReels } from "../api/client";
import type { ReelResponse } from "../types";
import SearchBar from "../components/SearchBar";
import ReelCard from "../components/ReelCard";

export default function Home() {
  const [reels, setReels] = useState<ReelResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listReels()
      .then((data) => setReels(data.reels))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load reels"),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <SearchBar />

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          Saved Reels
        </h2>
        {reels.length > 0 && (
          <span className="text-xs text-gray-400">{reels.length} reels</span>
        )}
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && reels.length === 0 && (
        <div className="py-16 text-center">
          <p className="text-gray-500">No reels saved yet.</p>
          <p className="mt-1 text-sm text-gray-400">
            Tap the <span className="font-medium text-indigo-600">+</span> button to save your first reel.
          </p>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {reels.map((reel) => (
          <ReelCard key={reel.id} reel={reel} />
        ))}
      </div>
    </div>
  );
}
