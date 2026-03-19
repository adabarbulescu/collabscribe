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
        <span className="toolbar__eyebrow">Collaborative writing workspace</span>
        <span className="toolbar__title">Collabscribe</span>
        <span className="toolbar__docid">doc/{documentId}</span>
      </div>

      <div className="toolbar__status-group">
        <span className="toolbar__meta toolbar__pill" aria-live="polite">
          {userCount} {userCount === 1 ? "collaborator" : "collaborators"}
        </span>

        <span className="connection-status toolbar__pill" role="status" aria-live="polite">
          <span
            className={
              connectionStatus === "connected"
                ? "connection-status__dot is-connected"
                : "connection-status__dot"
            }
            aria-hidden="true"
          />
          <span>{connectionStatus === "connected" ? "Live sync on" : "Reconnecting"}</span>
        </span>
      </div>

      <div className="toolbar__action-group">
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
      </div>

      <button type="button" className="toolbar__button toolbar__button--status toolbar__pill" disabled>
        {lastSaveLabel}
      </button>

      <button
        type="button"
        className={
          sidebarOpen
            ? "toolbar__button toolbar__button--toggle is-active"
            : "toolbar__button toolbar__button--ghost toolbar__button--toggle"
        }
        aria-expanded={sidebarOpen}
        aria-controls="analytics-sidebar"
        onClick={onToggleSidebar}
      >
        {sidebarOpen ? "Insights" : "Insights"}
      </button>
    </header>
  );
}
