import { useState } from "react";

import AnalyticsSidebar from "./components/AnalyticsSidebar";
import MobileViewToggle from "./components/MobileViewToggle";
import Toolbar from "./components/Toolbar";
import Workspace from "./components/Workspace";

const tabs = ["metrics", "analysis", "insights", "compare"];

export default function App() {
  const [activeTab, setActiveTab] = useState("metrics");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileView, setMobileView] = useState("split");

  return (
    <div className={`app-shell mobile-view-${mobileView}`}>
      <a href="#editor-region" className="skip-link">
        Skip to editor
      </a>

      <Toolbar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
      />

      <MobileViewToggle currentView={mobileView} onChange={setMobileView} />

      <div className="workspace-frame">
        <Workspace mobileView={mobileView} />
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
