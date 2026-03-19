import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react";
import { getEntity, getRelatedEntities } from "../api/client";
import type { EntityWithReels, RelatedEntity } from "../types";

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

export default function EntityDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [entity, setEntity] = useState<EntityWithReels | null>(null);
  const [related, setRelated] = useState<RelatedEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([getEntity(id), getRelatedEntities(id)])
      .then(([e, r]) => {
        setEntity(e);
        setRelated(r);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (error || !entity) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
        {error || "Entity not found"}
      </div>
    );
  }

  const color = typeColors[entity.type] ?? "bg-gray-100 text-gray-700";
  const attrs = Object.entries(entity.attributes || {});

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
        <div>
          <h1 className="text-lg font-semibold">{entity.name}</h1>
          <div className="mt-0.5 flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${color}`}
            >
              {entity.type}
            </span>
            <span className="text-xs text-gray-400">
              {entity.mention_count} mention
              {entity.mention_count !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
      </div>

      {/* Attributes */}
      {attrs.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Attributes
          </h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {attrs.map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs text-gray-400 capitalize">{key}</dt>
                <dd className="text-gray-700">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Related entities */}
      {related.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Related Entities
          </h3>
          <div className="space-y-2">
            {related.map((r) => (
              <Link
                key={r.id}
                to={`/entities/${r.id}`}
                className="flex items-center gap-2 rounded-lg p-2 transition hover:bg-gray-50"
              >
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                    typeColors[r.type] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {r.type}
                </span>
                <span className="flex-1 text-sm text-gray-700">{r.name}</span>
                <span className="text-xs text-gray-400">
                  {r.relation_type.replace(/_/g, " ")}
                </span>
                <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                  {r.strength}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Linked reels */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Appears in {entity.linked_reels.length} reel
          {entity.linked_reels.length !== 1 ? "s" : ""}
        </h3>
        <div className="space-y-2">
          {entity.linked_reels.map((reel) => (
            <Link
              key={reel.post_id}
              to={`/reels/${reel.post_id}`}
              className="block rounded-xl border border-gray-200 bg-white p-4 transition hover:border-indigo-200 hover:shadow-sm"
            >
              {reel.ai_summary && (
                <p className="text-sm text-gray-700 line-clamp-2">
                  {reel.ai_summary}
                </p>
              )}
              <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
                <span className="capitalize">
                  {reel.relationship?.replace(/_/g, " ")}
                </span>
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
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
