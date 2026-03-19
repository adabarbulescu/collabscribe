const tabLabels = {
  metrics: "Metrics",
  analysis: "Analysis",
  insights: "Insights",
  compare: "Compare"
};

function MetricCard({ label, value, subvalue }) {
  return (
    <div className="analytics-metric-card">
      <div className="analytics-metric-card__label">{label}</div>
      <div className="analytics-metric-card__value">{value}</div>
      {subvalue ? <div className="analytics-metric-card__subvalue">{subvalue}</div> : null}
    </div>
  );
}

function Placeholder({ children }) {
  return (
    <div className="analytics-placeholder-card">
      <p>{children}</p>
    </div>
  );
}

function MetricsPanel({ analytics }) {
  const metrics = analytics?.basic_metrics;
  const readability = analytics?.readability;

  if (!metrics) {
    return <Placeholder>Start typing to compute document metrics.</Placeholder>;
  }

  return (
    <div className="analytics-panel__stack">
      <div className="analytics-metrics-grid">
        <MetricCard label="Words" value={metrics.word_count} />
        <MetricCard
          label="Reading Time"
          value={`${metrics.reading_time_minutes || 0} min`}
        />
        <MetricCard
          label="Characters"
          value={metrics.char_count}
          subvalue={`${metrics.char_count_no_spaces} without spaces`}
        />
        <MetricCard
          label="Sentences"
          value={metrics.sentence_count}
          subvalue={`${metrics.avg_sentence_length} words/sentence`}
        />
        <MetricCard label="Paragraphs" value={metrics.paragraph_count} />
        <MetricCard label="Lines" value={metrics.line_count} />
      </div>

      <div>
        <p className="analytics-panel__label">Readability</p>
        {readability ? (
          <div className="analytics-detail-card">
            <div className="analytics-detail-card__row">
              <strong>{readability.label}</strong>
              <span>{readability.flesch_reading_ease}/100</span>
            </div>
            <div className="analytics-progress">
              <div
                className={`analytics-progress__bar analytics-progress__bar--${readability.color}`}
                style={{ width: `${Math.max(0, Math.min(100, readability.flesch_reading_ease))}%` }}
              />
            </div>
            <div className="analytics-detail-card__row analytics-detail-card__row--muted">
              <span>Flesch-Kincaid grade</span>
              <span>{readability.flesch_kincaid_grade}</span>
            </div>
            <p className="analytics-detail-card__text">{readability.tooltip}</p>
          </div>
        ) : (
          <Placeholder>Add roughly 30 words to see readability scoring.</Placeholder>
        )}
      </div>
    </div>
  );
}

function AnalysisPanel({ analytics }) {
  const ner = analytics?.ner;
  const sentiment = analytics?.sentiment;
  const keywords = analytics?.keywords;
  const vocabulary = analytics?.vocabulary;
  const math = analytics?.math_analysis;

  return (
    <div className="analytics-panel__stack">
      <div>
        <p className="analytics-panel__label">Named Entities</p>
        {ner?.entity_groups?.length ? (
          <div className="analytics-list-card">
            {ner.entity_groups.slice(0, 4).map((group) => (
              <div key={group.label} className="analytics-list-card__group">
                <div className="analytics-list-card__heading">
                  {group.display_name} <span>{group.entities.length}</span>
                </div>
                <div className="analytics-chip-row">
                  {group.entities.slice(0, 6).map((entity) => (
                    <span key={`${group.label}-${entity.text}`} className="analytics-chip">
                      {entity.text} ({entity.count})
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Placeholder>Add more text to surface named entities.</Placeholder>
        )}
      </div>

      <div>
        <p className="analytics-panel__label">Sentiment</p>
        {sentiment ? (
          <div className="analytics-detail-card">
            <div className="analytics-detail-card__row">
              <strong>{sentiment.polarity_label}</strong>
              <span>{sentiment.polarity}</span>
            </div>
            <div className="analytics-detail-card__row analytics-detail-card__row--muted">
              <span>{sentiment.subjectivity_label}</span>
              <span>{sentiment.subjectivity}</span>
            </div>
            <p className="analytics-detail-card__text">{sentiment.interpretation}</p>
          </div>
        ) : (
          <Placeholder>Add around 20 words to estimate sentiment.</Placeholder>
        )}
      </div>

      <div>
        <p className="analytics-panel__label">Keywords</p>
        {keywords?.length ? (
          <div className="analytics-chip-row">
            {keywords.slice(0, 10).map((item) => (
              <span key={item.term} className="analytics-chip">
                {item.term} ({item.score.toFixed(2)})
              </span>
            ))}
          </div>
        ) : (
          <Placeholder>Add more text for keyword extraction.</Placeholder>
        )}
      </div>

      <div>
        <p className="analytics-panel__label">Vocabulary</p>
        {vocabulary ? (
          <div className="analytics-detail-card">
            <div className="analytics-detail-card__row">
              <span>Unique words</span>
              <strong>{vocabulary.unique_words}</strong>
            </div>
            <div className="analytics-detail-card__row analytics-detail-card__row--muted">
              <span>Type-token ratio</span>
              <span>{(vocabulary.type_token_ratio * 100).toFixed(1)}%</span>
            </div>
            <div className="analytics-detail-card__row analytics-detail-card__row--muted">
              <span>Lexical density</span>
              <span>{(vocabulary.lexical_density * 100).toFixed(1)}%</span>
            </div>
            <div className="analytics-chip-row">
              {vocabulary.top_words.slice(0, 8).map((word) => (
                <span key={word.word} className="analytics-chip">
                  {word.word} ({word.count})
                </span>
              ))}
            </div>
          </div>
        ) : (
          <Placeholder>Add around 20 words for vocabulary analysis.</Placeholder>
        )}
      </div>

      <div>
        <p className="analytics-panel__label">Math Content</p>
        {math && math.total_equations > 0 ? (
          <div className="analytics-detail-card">
            <div className="analytics-detail-card__row">
              <span>Total equations</span>
              <strong>{math.total_equations}</strong>
            </div>
            <div className="analytics-detail-card__row analytics-detail-card__row--muted">
              <span>Density</span>
              <span>{math.density_label}</span>
            </div>
            <div className="analytics-chip-row">
              {Object.entries(math.detected_structures || {})
                .filter(([, count]) => count > 0)
                .map(([structure, count]) => (
                  <span key={structure} className="analytics-chip">
                    {structure.replaceAll("_", " ")} ({count})
                  </span>
                ))}
            </div>
          </div>
        ) : (
          <Placeholder>No mathematical expressions detected.</Placeholder>
        )}
      </div>
    </div>
  );
}

function DeferredPanel({ title, body }) {
  return (
    <>
      <p className="analytics-panel__label">{title}</p>
      <Placeholder>{body}</Placeholder>
    </>
  );
}

export default function AnalyticsSidebar({
  activeTab,
  analytics,
  isOpen,
  tabs,
  onClose,
  onSelectTab
}) {
  const { data, error, isLoading } = analytics;

  return (
    <aside
      id="analytics-sidebar"
      className={isOpen ? "analytics-sidebar is-open" : "analytics-sidebar"}
      aria-label="Analytics dashboard"
      aria-hidden={!isOpen}
    >
      <div className="analytics-sidebar__header">
        <div>
          <p className="analytics-sidebar__eyebrow">Analytics connected</p>
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
        {isLoading && !data ? <Placeholder>Analyzing document...</Placeholder> : null}
        {error && !data ? <Placeholder>Analytics error: {error}</Placeholder> : null}
        {!isLoading && !error && activeTab === "metrics" ? <MetricsPanel analytics={data} /> : null}
        {!isLoading && !error && activeTab === "analysis" ? <AnalysisPanel analytics={data} /> : null}
        {activeTab === "insights" ? (
          <DeferredPanel
            title="Insights"
            body="Insights charts and temporal analytics are the next slice after core analytics."
          />
        ) : null}
        {activeTab === "compare" ? (
          <DeferredPanel
            title="Compare Versions"
            body="Version comparison and diff rendering are still pending migration."
          />
        ) : null}
      </section>
    </aside>
  );
}
