import CollaborativeEditor from "./CollaborativeEditor";

export default function Workspace({
  content,
  docId,
  mobileView,
  onChangeContent,
  onConnectionStatusChange,
  onLastSaveAt,
  onToast,
  onUserCountChange,
  previewHtml
}) {
  const editorHidden = mobileView === "preview";
  const previewHidden = mobileView === "editor";

  return (
    <main className="workspace" role="main">
      <section
        id="editor-region"
        className={`pane pane--editor${editorHidden ? " is-hidden-mobile" : ""}`}
        aria-label="Markdown editor"
      >
        <div className="pane__header">
          <span>Editor</span>
          <span className="pane__badge">Monaco + Yjs</span>
        </div>
        <div className="pane__body pane__body--editor">
          <CollaborativeEditor
            docId={docId}
            initialContent={content}
            onConnectionStatusChange={onConnectionStatusChange}
            onContentChange={onChangeContent}
            onLastSaveAt={onLastSaveAt}
            onToast={onToast}
            onUserCountChange={onUserCountChange}
          />
        </div>
      </section>

      <div className="workspace__divider" aria-hidden="true" />

      <section
        className={`pane pane--preview${previewHidden ? " is-hidden-mobile" : ""}`}
        aria-label="Live preview"
      >
        <div className="pane__header">
          <span>Preview</span>
          <span className="pane__badge pane__badge--muted">Rendered in React</span>
        </div>
        <div className="pane__body">
          <article
            className="preview-card preview-markdown"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        </div>
      </section>
    </main>
  );
}
