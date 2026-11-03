import { useEffect, useRef } from "react";

export default function PlanDeleteDialog({ planName, deleting, error, onCancel, onConfirm }) {
  const cancelButton = useRef(null);
  const deleteButton = useRef(null);

  useEffect(() => {
    cancelButton.current?.focus();
  }, []);

  function handleKeyDown(event) {
    if (event.key === "Escape" && !deleting) {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const first = cancelButton.current;
    const last = deleteButton.current;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <div className="user-plan-dialog-backdrop">
      <section
        className="user-plan-delete-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-plan-title"
        aria-describedby="delete-plan-description"
        onKeyDown={handleKeyDown}
      >
        <h2 id="delete-plan-title">Delete photography plan?</h2>
        <p id="delete-plan-description">
          Delete “{planName}”? This action can’t be undone.
        </p>
        {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
        <div className="user-plan-dialog-actions">
          <button
            ref={cancelButton}
            className="user-plan-action-secondary"
            type="button"
            onClick={onCancel}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            ref={deleteButton}
            className="user-plan-action-danger"
            type="button"
            onClick={onConfirm}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </section>
    </div>
  );
}
