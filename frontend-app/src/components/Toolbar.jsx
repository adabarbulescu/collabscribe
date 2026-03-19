const actions = [
  "Save Version",
  "Copy Share Link",
  "Export .md",
  "Export PDF"
];

export default function Toolbar({ sidebarOpen, onToggleSidebar }) {
  return (
    <header className="toolbar" role="toolbar" aria-label="Document actions">
      <span className="toolbar__title">Collabscribe</span>

      <span className="toolbar__meta" aria-live="polite">
        1 user
      </span>

      <span className="connection-status" role="status" aria-live="polite">
        <span className="connection-status__dot" aria-hidden="true" />
        <span>Disconnected</span>
      </span>

      {actions.map((label) => (
        <button key={label} type="button" className="toolbar__button toolbar__button--ghost">
          {label}
        </button>
      ))}

      <button type="button" className="toolbar__button toolbar__button--status">
        Never
      </button>

      <button
        type="button"
        className="toolbar__button"
        aria-expanded={sidebarOpen}
        aria-controls="analytics-sidebar"
        onClick={onToggleSidebar}
      >
        Analytics
      </button>
    </header>
  );
}
