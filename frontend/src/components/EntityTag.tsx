import { Link } from "react-router-dom";

const typeColors: Record<string, string> = {
  product: "bg-purple-50 text-purple-700",
  brand: "bg-blue-50 text-blue-700",
  place: "bg-emerald-50 text-emerald-700",
  person: "bg-orange-50 text-orange-700",
  style: "bg-pink-50 text-pink-700",
  book: "bg-amber-50 text-amber-700",
  recipe: "bg-rose-50 text-rose-700",
  exercise: "bg-teal-50 text-teal-700",
};

interface Props {
  id: string;
  name: string;
  type: string;
}

export default function EntityTag({ id, name, type }: Props) {
  const color = typeColors[type] ?? "bg-gray-100 text-gray-700";
  return (
    <Link
      to={`/entities/${id}`}
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium transition hover:opacity-80 ${color}`}
    >
      {name}
    </Link>
  );
}
