const views = [
  { id: "editor", label: "Editor" },
  { id: "split", label: "Split" },
  { id: "preview", label: "Preview" }
];

export default function MobileViewToggle({ currentView, onChange }) {
  return (
    <div className="mobile-toggle" role="group" aria-label="Mobile workspace view">
      {views.map((view) => (
        <button
          key={view.id}
          type="button"
          className={view.id === currentView ? "mobile-toggle__button is-active" : "mobile-toggle__button"}
          onClick={() => onChange(view.id)}
        >
          {view.label}
        </button>
      ))}
    </div>
  );
}
