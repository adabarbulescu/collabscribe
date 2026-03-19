import { Suspense, lazy, useEffect, useRef, useState } from "react";

const CollaborativeEditor = lazy(() => import("./CollaborativeEditor"));

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
  const [editorWidth, setEditorWidth] = useState(50);
  const workspaceRef = useRef(null);
  const editorHidden = mobileView === "preview";
  const previewHidden = mobileView === "editor";

  useEffect(() => {
    function stopResize() {
      document.body.classList.remove("is-resizing");
    }

    window.addEventListener("pointerup", stopResize);
    return () => window.removeEventListener("pointerup", stopResize);
  }, []);

  function startResize(event) {
    if (window.innerWidth <= 768 || !workspaceRef.current) {
      return;
    }

    document.body.classList.add("is-resizing");

    const bounds = workspaceRef.current.getBoundingClientRect();

    function handlePointerMove(moveEvent) {
      const nextWidth = ((moveEvent.clientX - bounds.left) / bounds.width) * 100;
      const clampedWidth = Math.min(70, Math.max(30, nextWidth));
      setEditorWidth(clampedWidth);
    }

    function handlePointerUp() {
      document.body.classList.remove("is-resizing");
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    event.preventDefault();
  }

  return (
    <main
      ref={workspaceRef}
      className="workspace"
      role="main"
      style={{ "--editor-width": `${editorWidth}%`, "--preview-width": `${100 - editorWidth}%` }}
    >
      <section
        id="editor-region"
        className={`pane pane--editor${editorHidden ? " is-hidden-mobile" : ""}`}
        aria-label="Markdown editor"
      >
        <div className="pane__header">
          <span>Editor</span>
        </div>
        <div className="pane__body pane__body--editor">
          <Suspense
            fallback={
              <div className="editor-loading-card">
                <strong>Loading editor...</strong>
                <span>Monaco and collaboration services are initializing.</span>
              </div>
            }
          >
            <CollaborativeEditor
              docId={docId}
              initialContent={content}
              onConnectionStatusChange={onConnectionStatusChange}
              onContentChange={onChangeContent}
              onLastSaveAt={onLastSaveAt}
              onToast={onToast}
              onUserCountChange={onUserCountChange}
            />
          </Suspense>
        </div>
      </section>

      <button
        type="button"
        className="workspace__divider"
        aria-label="Resize editor and preview panels"
        aria-orientation="vertical"
        onPointerDown={startResize}
      />

      <section
        className={`pane pane--preview${previewHidden ? " is-hidden-mobile" : ""}`}
        aria-label="Live preview"
      >
        <div className="pane__header">
          <span>Preview</span>
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
