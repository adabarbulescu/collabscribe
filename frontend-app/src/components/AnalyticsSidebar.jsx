const tabLabels = {
  metrics: "Metrics",
  analysis: "Analysis",
  insights: "Insights",
  compare: "Compare"
};

const panelContent = {
  metrics: {
    title: "Document Statistics",
    body:
      "Metric cards and readability charts will be migrated here after the editor and preview are live in React."
  },
  analysis: {
    title: "Analysis",
    body:
      "Named entities, sentiment, topics, keywords, vocabulary, and math analysis remain in the legacy frontend until the analytics slice."
  },
  insights: {
    title: "Insights",
    body:
      "Session charts and temporal analytics will be ported after collaboration and version history are stable."
  },
  compare: {
    title: "Compare Versions",
    body:
      "The diff workflow is intentionally deferred until the core editor and analytics state are moved over."
  }
};

export default function AnalyticsSidebar({
  activeTab,
  isOpen,
  tabs,
  onClose,
  onSelectTab
}) {
  const content = panelContent[activeTab];

  return (
    <aside
      id="analytics-sidebar"
      className={isOpen ? "analytics-sidebar is-open" : "analytics-sidebar"}
      aria-label="Analytics dashboard"
      aria-hidden={!isOpen}
    >
      <div className="analytics-sidebar__header">
        <div>
          <p className="analytics-sidebar__eyebrow">Shell migrated</p>
          <h2>Analytics</h2>
        </div>
        <button type="button" className="analytics-sidebar__close" onClick={onClose}>
          Close
        </button>
      </div>

      <nav className="analytics-tabs" role="tablist" aria-label="Analytics tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            className={activeTab === tab ? "analytics-tabs__button is-active" : "analytics-tabs__button"}
            onClick={() => onSelectTab(tab)}
          >
            {tabLabels[tab]}
          </button>
        ))}
      </nav>

      <section className="analytics-panel" role="tabpanel">
        <p className="analytics-panel__label">{content.title}</p>
        <div className="analytics-placeholder-card">
          <p>{content.body}</p>
        </div>
      </section>
    </aside>
  );
}
