import { useMemo, useState } from "react";

import "katex/dist/katex.min.css";

import AnalyticsSidebar from "./components/AnalyticsSidebar";
import MobileViewToggle from "./components/MobileViewToggle";
import Toolbar from "./components/Toolbar";
import Workspace from "./components/Workspace";
import { getDocumentId } from "./lib/document";
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

## Why this step matters

- The app shell now lives in React.
- The editor and preview flow now lives in React too.
- Monaco, Yjs, saving, analytics, and diffing are the next migration slices.
`;

export default function App() {
  const [activeTab, setActiveTab] = useState("metrics");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileView, setMobileView] = useState("split");
  const [content, setContent] = useState(initialDocument);

  const docId = useMemo(() => getDocumentId(window.location.pathname), []);
  const previewHtml = useMemo(() => renderPreviewHtml(content), [content]);

  return (
    <div className={`app-shell mobile-view-${mobileView}`}>
      <a href="#editor-region" className="skip-link">
        Skip to editor
      </a>

      <Toolbar
        documentId={docId}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
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
    </div>
  );
}
