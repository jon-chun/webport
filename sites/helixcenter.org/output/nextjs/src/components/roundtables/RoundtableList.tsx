import { RoundtableCard } from "./RoundtableCard";

interface RoundtableListProps {
  roundtables: Parameters<typeof RoundtableCard>[0]["roundtable"][];
}

export function RoundtableList({ roundtables }: RoundtableListProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      {roundtables.map((rt) => (
        <RoundtableCard key={rt.id} roundtable={rt} />
      ))}
    </div>
  );
}
