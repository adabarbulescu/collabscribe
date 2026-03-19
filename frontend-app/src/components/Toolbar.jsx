const actions = [
  { id: "save", label: "Save Version" },
  { id: "share", label: "Copy Share Link" },
  { id: "markdown", label: "Export .md" },
  { id: "pdf", label: "Export PDF" }
];

export default function Toolbar({
  connectionStatus,
  documentId,
  isSaving,
  lastSaveLabel,
  onCopyLink,
  onExportMarkdown,
  onExportPdf,
  onSaveVersion,
  onToggleSidebar,
  sidebarOpen,
  userCount
}) {
  const handlers = {
    save: onSaveVersion,
    share: onCopyLink,
    markdown: onExportMarkdown,
    pdf: onExportPdf
  };

  return (
    <header className="toolbar" role="toolbar" aria-label="Document actions">
      <div className="toolbar__identity">
        <span className="toolbar__title">Collabscribe</span>
        <span className="toolbar__docid">doc/{documentId}</span>
      </div>

      <span className="toolbar__meta" aria-live="polite">
        {userCount} {userCount === 1 ? "user" : "users"}
      </span>

      <span className="connection-status" role="status" aria-live="polite">
        <span
          className={
            connectionStatus === "connected"
              ? "connection-status__dot is-connected"
              : "connection-status__dot"
          }
          aria-hidden="true"
        />
        <span>{connectionStatus === "connected" ? "Connected" : "Disconnected"}</span>
      </span>

      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          className={action.id === "save" ? "toolbar__button" : "toolbar__button toolbar__button--ghost"}
          onClick={handlers[action.id]}
          disabled={action.id === "save" && isSaving}
        >
          {action.id === "save" && isSaving ? "Saving..." : action.label}
        </button>
      ))}

      <button type="button" className="toolbar__button toolbar__button--status" disabled>
        {lastSaveLabel}
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
