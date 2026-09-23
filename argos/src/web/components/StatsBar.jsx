import { STATUS_LABELS } from '../labels.js';

export default function StatsBar({ stats }) {
  if (!stats) return null;
  return (
    <ul className="stats">
      {Object.entries(STATUS_LABELS).map(([status, label]) => (
        <li key={status}>
          {label} <strong>{stats[status]}</strong>
        </li>
      ))}
      <li>
        Total <strong>{stats.total}</strong>
      </li>
    </ul>
  );
}
