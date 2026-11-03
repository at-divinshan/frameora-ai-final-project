import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, MapPin, Pencil, Sparkles, Trash2, Users } from "lucide-react";
import PlanDeleteDialog from "./PlanDeleteDialog";
import {
  deletePlan,
  getPlanErrorMessage,
  getPlanSuggestions,
  getSuggestionErrorMessage,
} from "../../services/planService";

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
  const entries = preferenceLabels.flatMap(([key, label]) => {
    const item = Object.hasOwn(value, key) ? value[key] : null;
    // Ignore malformed structured values; React safely escapes displayed text.
    if (typeof item !== "string" && typeof item !== "number" && typeof item !== "boolean") return [];
    const text = String(item).trim();
    return text ? [[key, label, text]] : [];
  });
  const equipment = value.equipment;
  if (equipment && typeof equipment === "object" && !Array.isArray(equipment)) {
    const parts = [];
    if (typeof equipment.device_type === "string") parts.push(equipment.device_type);
    if (typeof equipment.camera_model === "string" && equipment.camera_model.trim()) parts.push(equipment.camera_model.trim());
    if (typeof equipment.lens === "string" && equipment.lens.trim()) parts.push(`Lens: ${equipment.lens.trim()}`);
    if (typeof equipment.additional_equipment === "string" && equipment.additional_equipment.trim()) {
      parts.push(`Additional equipment: ${equipment.additional_equipment.trim()}`);
    }
    if (parts.length) entries.push(["equipment", "Photography Equipment", parts.join(" · ")]);
  }
  return entries;
}

const suggestionCategories = [
  ["pose_suggestions", "Pose Suggestions"],
  ["camera_angles", "Camera Angles"],
  ["lighting_tips", "Lighting Tips"],
  ["camera_settings", "Camera Settings"],
  ["composition_tips", "Composition Tips"],
  ["photography_tools", "Photography Tools"],
];

export default function PlanCard({ plan, onDeleted }) {
  const preferences = preferenceEntries(plan.preferences);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [suggestions, setSuggestions] = useState(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState("");
  const deleteTrigger = useRef(null);
  const hadDialog = useRef(false);

  useEffect(() => {
    if (confirmingDelete) hadDialog.current = true;
    else if (hadDialog.current) {
      deleteTrigger.current?.focus();
      hadDialog.current = false;
    }
  }, [confirmingDelete]);

  async function confirmDelete() {
    setDeleting(true);
    setDeleteError("");
    try {
      await deletePlan(plan.id);
      setConfirmingDelete(false);
      onDeleted(plan.id);
    } catch (error) {
      setDeleteError(getPlanErrorMessage(error, "delete"));
    } finally {
      setDeleting(false);
    }
  }

  async function loadSuggestions() {
    setSuggestionsLoading(true);
    setSuggestionsError("");
    try {
      setSuggestions(await getPlanSuggestions(plan.id));
    } catch (error) {
      setSuggestionsError(getSuggestionErrorMessage(error));
    } finally {
      setSuggestionsLoading(false);
    }
  }

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
      <div className="user-plan-card-actions">
        <button
          className="user-plan-action-secondary"
          type="button"
          onClick={loadSuggestions}
          disabled={suggestionsLoading}
          aria-label={`Get AI suggestions for ${plan.photography_type} plan`}
        >
          <Sparkles size={15} aria-hidden="true" /> {suggestionsLoading ? "Getting Suggestions…" : "AI Suggestions"}
        </button>
        <Link
          className="user-dashboard-create-button"
          to={`/user/plans/${plan.id}/edit`}
          aria-label={`Edit ${plan.photography_type} plan`}
        >
          <Pencil size={15} aria-hidden="true" /> Edit
        </Link>
        <button
          ref={deleteTrigger}
          className="user-plan-action-secondary"
          type="button"
          onClick={() => {
            setDeleteError("");
            setConfirmingDelete(true);
          }}
          aria-label={`Delete ${plan.photography_type} plan`}
        >
          <Trash2 size={15} aria-hidden="true" /> Delete
        </button>
      </div>
      {suggestionsError && <p className="user-plan-message is-error" role="alert">{suggestionsError}</p>}
      {suggestions && (
        <section className="user-plan-suggestions" aria-label="AI photography suggestions" aria-live="polite">
          {suggestionCategories.map(([key, label]) => (
            <div key={key}>
              <h3>{label}</h3>
              <ul>
                {suggestions[key].map((suggestion, index) => <li key={`${key}-${index}`}>{suggestion}</li>)}
              </ul>
            </div>
          ))}
        </section>
      )}
      {confirmingDelete && (
        <PlanDeleteDialog
          planName={plan.photography_type}
          deleting={deleting}
          error={deleteError}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={confirmDelete}
        />
      )}
    </article>
  );
}