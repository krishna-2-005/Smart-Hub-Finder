import type { Cluster } from "../../api/types";

export function ClusterSelector({
  id,
  value,
  onChange,
  clusters,
  includeAuto = true,
  includeAll = true,
  label = "Cluster",
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  clusters: Cluster[];
  includeAuto?: boolean;
  includeAll?: boolean;
  label?: string;
}) {
  const sorted = [...clusters].sort((a, b) => a.display_name.localeCompare(b.display_name));
  return (
    <div>
      <label htmlFor={id} className="label mb-1">
        {label}
      </label>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {includeAuto && <option value="auto">Auto-detect from location</option>}
        {includeAll && <option value="all">All clusters</option>}
        {sorted.map((c) => (
          <option key={c.cluster_id} value={c.cluster_id}>
            {c.display_name} ({c.hub_count} hubs)
          </option>
        ))}
      </select>
    </div>
  );
}
