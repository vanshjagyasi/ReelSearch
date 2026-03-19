import { useEffect, useState, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Loader2, ExternalLink, Film } from "lucide-react";
import { searchReels } from "../api/client";
import type { SearchResult } from "../types";
import SearchBar from "../components/SearchBar";
import PlatformIcon from "../components/PlatformIcon";

const MAX_TAGS = 5;

export default function SearchResults() {
  const [params] = useSearchParams();
  const query = params.get("q") ?? "";
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!query) return;
    setLoading(true);
    setError("");
    searchReels(query)
      .then((data) => setResults(data.results))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Search failed"),
      )
      .finally(() => setLoading(false));
  }, [query]);

  return (
    <div className="space-y-4">
      <SearchBar initialQuery={query} autoFocus />

      {!query && (
        <div className="py-16 text-center">
          <p className="text-gray-500">
            Search your saved reels with natural language.
          </p>
          <p className="mt-1 text-sm text-gray-400">
            Try "budget home decor ideas" or "pasta recipes"
          </p>
        </div>
      )}

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

      {query && !loading && !error && results.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-gray-500">No results found.</p>
          <p className="mt-1 text-sm text-gray-400">
            Try a different query or save more reels.
          </p>
        </div>
      )}

      {results.length > 0 && (
        <p className="text-xs text-gray-400">
          {results.length} result{results.length !== 1 ? "s" : ""}
        </p>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {results.map((r) => (
          <ResultCard key={r.post_id} result={r} />
        ))}
      </div>
    </div>
  );
}

function ResultCard({ result: r }: { result: SearchResult }) {
  const title =
    r.caption?.split("\n")[0]?.slice(0, 100) ||
    r.ai_summary?.slice(0, 100) ||
    r.url;
  const tags = r.ai_tags.slice(0, MAX_TAGS);

  return (
    <Link
      to={`/reels/${r.post_id}`}
      className="flex gap-3 rounded-xl border border-gray-200 bg-white p-3 transition hover:border-indigo-200 hover:shadow-sm"
    >
      {/* Thumbnail */}
      <Thumbnail thumbnailUrl={r.thumbnail_url} />

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <div>
          {/* Platform + creator */}
          <div className="flex items-center gap-1.5">
            <PlatformIcon platform={r.platform} />
            {r.creator && (
              <span className="truncate text-xs text-gray-500">
                @{r.creator}
              </span>
            )}
          </div>

          {/* Title */}
          <p className="mt-1 text-sm font-medium leading-snug text-gray-800 line-clamp-2">
            {title}
          </p>
        </div>

        {/* Tags */}
        {tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500"
              >
                {tag}
              </span>
            ))}
            {r.ai_tags.length > MAX_TAGS && (
              <span className="rounded-full bg-gray-50 px-2 py-0.5 text-[11px] text-gray-400">
                +{r.ai_tags.length - MAX_TAGS}
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-gray-400">
          {r.matched_entities.length > 0 && (
            <span className="truncate text-indigo-500">
              {r.matched_entities.join(", ")}
            </span>
          )}
          <a
            href={r.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="ml-auto flex flex-shrink-0 items-center gap-1 text-indigo-500 hover:text-indigo-600"
          >
            Open <ExternalLink size={10} />
          </a>
        </div>
      </div>
    </Link>
  );
}

function Thumbnail({ thumbnailUrl }: { thumbnailUrl: string | null }) {
  const [failed, setFailed] = useState(false);

  const handleError = useCallback(() => setFailed(true), []);

  return (
    <div className="h-24 w-20 flex-shrink-0 overflow-hidden rounded-lg bg-gray-100 md:h-28 md:w-24">
      {!failed && thumbnailUrl ? (
        <img
          src={thumbnailUrl}
          alt=""
          className="h-full w-full object-cover"
          onError={handleError}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-gray-300">
          <Film size={24} />
        </div>
      )}
    </div>
  );
}
