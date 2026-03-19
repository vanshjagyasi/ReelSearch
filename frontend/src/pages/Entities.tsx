import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { listEntities } from "../api/client";
import type { EntityResponse } from "../types";

const ENTITY_TYPES = [
  "all",
  "product",
  "brand",
  "place",
  "person",
  "style",
  "book",
  "recipe",
  "exercise",
] as const;

const typeColors: Record<string, string> = {
  product: "bg-purple-100 text-purple-700",
  brand: "bg-blue-100 text-blue-700",
  place: "bg-emerald-100 text-emerald-700",
  person: "bg-orange-100 text-orange-700",
  style: "bg-pink-100 text-pink-700",
  book: "bg-amber-100 text-amber-700",
  recipe: "bg-rose-100 text-rose-700",
  exercise: "bg-teal-100 text-teal-700",
};

export default function Entities() {
  const [entities, setEntities] = useState<EntityResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    setError("");
    listEntities(typeFilter === "all" ? undefined : typeFilter)
      .then(setEntities)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, [typeFilter]);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Entities</h1>

      {/* Type filter pills */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-4 px-4 md:mx-0 md:px-0 md:flex-wrap">
        {ENTITY_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`flex-shrink-0 rounded-full px-3 py-1 text-xs font-medium capitalize transition ${
              typeFilter === t
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {t}
          </button>
        ))}
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

      {!loading && !error && entities.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-gray-500">No entities found.</p>
          <p className="mt-1 text-sm text-gray-400">
            Save and process reels to build the knowledge graph.
          </p>
        </div>
      )}

      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
        {entities.map((entity) => (
          <Link
            key={entity.id}
            to={`/entities/${entity.id}`}
            className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 transition hover:border-indigo-200 hover:shadow-sm"
          >
            <span
              className={`flex-shrink-0 rounded-lg px-2 py-1 text-[10px] font-bold uppercase ${
                typeColors[entity.type] ?? "bg-gray-100 text-gray-700"
              }`}
            >
              {entity.type}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-800">
                {entity.name}
              </p>
            </div>
            <span className="flex-shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
              {entity.mention_count}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
