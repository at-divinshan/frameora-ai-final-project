import { CalendarDays, MapPin, Users } from "lucide-react";

function formatDate(value) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not scheduled"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

const preferenceLabels = [
  ["photography_style", "Photography Style"],
  ["lighting_preference", "Lighting"],
  ["pose_preference", "Pose"],
  ["camera_angle_preference", "Camera Angle"],
  ["outfit_color", "Outfit Color"],
];

function preferenceEntries(value) {
  if (typeof value === "string") {
    try { value = JSON.parse(value); } catch { return []; }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return preferenceLabels.flatMap(([key, label]) => {
    const item = Object.hasOwn(value, key) ? value[key] : null;
    // Ignore malformed structured values; React safely escapes displayed text.
    if (typeof item !== "string" && typeof item !== "number" && typeof item !== "boolean") return [];
    const text = String(item).trim();
    return text ? [[key, label, text]] : [];
  });
}

export default function PlanCard({ plan }) {
  const preferences = preferenceEntries(plan.preferences);
  return (
    <article className="user-plan-card">
      <div className="user-plan-card-heading">
        <div>
          <p className="user-plan-type">{plan.photography_type}</p>
          <h2>{plan.environment}</h2>
        </div>
        <span className="user-plan-people"><Users size={16} aria-hidden="true" /> {plan.people_count}</span>
      </div>
      <dl className="user-plan-details">
        <div><dt><CalendarDays size={15} aria-hidden="true" /> Shoot</dt><dd>{formatDate(plan.shoot_datetime)}</dd></div>
        {plan.location && <div><dt><MapPin size={15} aria-hidden="true" /> Location</dt><dd>{plan.location}</dd></div>}
      </dl>
      {preferences.length > 0 && (
        <details className="user-plan-preferences">
          <summary>Preferences</summary>
          <dl className="user-plan-preference-list">
            {preferences.map(([key, label, value]) => (
              <div key={key}><dt>{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
        </details>
      )}
    </article>
  );
}