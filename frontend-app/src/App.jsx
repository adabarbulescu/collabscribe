import { useEffect, useMemo, useState } from "react";

import "katex/dist/katex.min.css";

import AnalyticsSidebar from "./components/AnalyticsSidebar";
import MobileViewToggle from "./components/MobileViewToggle";
import Toast from "./components/Toast";
import Toolbar from "./components/Toolbar";
import Workspace from "./components/Workspace";
import { exportAsMarkdown, exportAsPdf, shareDocumentLink } from "./lib/actions";
import { getDocumentId } from "./lib/document";
import { useDocumentSession } from "./lib/useDocumentSession";
import { renderPreviewHtml } from "./lib/markdown";

const tabs = ["metrics", "analysis", "insights", "compare"];

const initialDocument = `# Collabscribe

Write in Markdown on the left and see the rendered preview on the right.

## Live math

Inline math: $E = mc^2$

Display math:

$$
\\int_0^1 x^2 \\, dx = \\frac{1}{3}
$$

## React migration progress

- App shell migrated
- Editor and preview migrated
- Versioning and session status are now wired to the backend
- Monaco, Yjs syncing, analytics, and compare flows are next
`;

export default function App() {
  const [activeTab, setActiveTab] = useState("metrics");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileView, setMobileView] = useState("split");
  const [content, setContent] = useState(initialDocument);
  const [toast, setToast] = useState(null);

  const docId = useMemo(() => getDocumentId(window.location.pathname), []);
  const previewHtml = useMemo(() => renderPreviewHtml(content), [content]);

  const {
    connectionStatus,
    isSaving,
    lastSaveLabel,
    saveVersion,
    userCount
  } = useDocumentSession({
    content,
    docId,
    onRestoreContent: setContent,
    onToast: setToast
  });

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  return (
    <div className={`app-shell mobile-view-${mobileView}`}>
      <a href="#editor-region" className="skip-link">
        Skip to editor
      </a>

      <Toolbar
        connectionStatus={connectionStatus}
        documentId={docId}
        isSaving={isSaving}
        lastSaveLabel={lastSaveLabel}
        onCopyLink={() => shareDocumentLink(window.location.href, setToast)}
        onExportMarkdown={() => exportAsMarkdown(content, docId, setToast)}
        onExportPdf={() => exportAsPdf(docId, previewHtml, setToast)}
        onSaveVersion={() => saveVersion()}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
        sidebarOpen={sidebarOpen}
        userCount={userCount}
      />

      <MobileViewToggle currentView={mobileView} onChange={setMobileView} />

      <div className="workspace-frame">
        <Workspace
          content={content}
          mobileView={mobileView}
          onChangeContent={setContent}
          previewHtml={previewHtml}
        />
        <AnalyticsSidebar
          activeTab={activeTab}
          isOpen={sidebarOpen}
          tabs={tabs}
          onClose={() => setSidebarOpen(false)}
          onSelectTab={setActiveTab}
        />
      </div>

      <Toast message={toast} />
    </div>
  );
}
