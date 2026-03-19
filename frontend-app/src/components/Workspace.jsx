export default function Workspace({ mobileView }) {
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
          <span className="pane__badge">Migration target</span>
        </div>
        <div className="pane__body pane__body--editor">
          <div className="editor-placeholder">
            <p>Monaco, Yjs, and versioning hooks move here in the next slice.</p>
            <pre>
              <code>{`# Collabscribe\n\nReact shell is ready.\n\n- editor parity pending\n- preview parity pending`}</code>
            </pre>
          </div>
        </div>
      </section>

      <div className="workspace__divider" aria-hidden="true" />

      <section
        className={`pane pane--preview${previewHidden ? " is-hidden-mobile" : ""}`}
        aria-label="Live preview"
      >
        <div className="pane__header">
          <span>Preview</span>
          <span className="pane__badge pane__badge--muted">Static placeholder</span>
        </div>
        <div className="pane__body">
          <article className="preview-card">
            <h1>Preview parity comes next</h1>
            <p>
              This step only moves the shell into React. Markdown rendering,
              KaTeX, and synchronization are intentionally not wired yet.
            </p>
            <ul>
              <li>Shared workspace layout is now componentized.</li>
              <li>Toolbar and sidebar controls are in React state.</li>
              <li>Legacy frontend remains the runtime fallback.</li>
            </ul>
          </article>
        </div>
      </section>
    </main>
  );
}
