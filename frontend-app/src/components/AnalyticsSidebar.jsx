const tabLabels = {
  metrics: "Metrics",
  analysis: "Analysis",
  insights: "Insights",
  compare: "Compare"
};

function formatDate(value) {
  if (!value) {
    return "Unavailable";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatMetric(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "0";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

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
      <span className="analytics-placeholder-card__eyebrow">Writer guidance</span>
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

function MiniLineChart({ points, metricKey, color, formatter }) {
  if (!points?.length) {
    return null;
  }

  const width = 280;
  const height = 120;
  const padding = 16;
  const values = points.map((point) => point[metricKey] ?? 0);
  const maxValue = Math.max(...values, 1);
  const stepX = points.length === 1 ? 0 : (width - padding * 2) / (points.length - 1);

  const polyline = points
    .map((point, index) => {
      const x = padding + index * stepX;
      const y = height - padding - ((point[metricKey] ?? 0) / maxValue) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="analytics-chart-card">
      <svg
        className="analytics-chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${metricKey} timeline`}
      >
        <polyline
          fill="none"
          points={polyline}
          stroke={color}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
        {points.map((point, index) => {
          const x = padding + index * stepX;
          const y = height - padding - ((point[metricKey] ?? 0) / maxValue) * (height - padding * 2);

          return (
            <circle key={`${metricKey}-${point.version_number}`} cx={x} cy={y} fill={color} r="4">
              <title>{`v${point.version_number}: ${formatter(point[metricKey] ?? 0)}`}</title>
            </circle>
          );
        })}
      </svg>
      <div className="analytics-chart-card__footer">
        <span>{`v${points[0].version_number}`}</span>
        <span>{`v${points[points.length - 1].version_number}`}</span>
      </div>
    </div>
  );
}

function InsightsPanel({ insights }) {
  const { data, error, isLoading } = insights;
  const timeline = data?.timeline || [];
  const stats = data?.stats;

  if (isLoading && !data) {
    return <Placeholder>Loading document insights...</Placeholder>;
  }

  if (error && !data) {
    return <Placeholder>Insights error: {error}</Placeholder>;
  }

  if (!timeline.length) {
    return <Placeholder>Save a few versions to unlock document insights over time.</Placeholder>;
  }

  return (
    <div className="analytics-panel__stack">
      <div className="analytics-metrics-grid">
        <MetricCard label="Versions" value={stats?.total_versions || timeline.length} />
        <MetricCard label="Net Words" value={formatMetric(stats?.net_words || 0)} />
        <MetricCard label="Average WPM" value={formatMetric(stats?.avg_wpm || 0, 2)} />
        <MetricCard label="Last Version" value={stats?.last_version_number || timeline[timeline.length - 1].version_number} />
      </div>

      <div>
        <p className="analytics-panel__label">Writing Timeline</p>
        <div className="analytics-detail-card">
          <div className="analytics-detail-card__row analytics-detail-card__row--muted">
            <span>Started</span>
            <span>{formatDate(stats?.start_time)}</span>
          </div>
          <div className="analytics-detail-card__row analytics-detail-card__row--muted">
            <span>Latest version</span>
            <span>{formatDate(stats?.end_time)}</span>
          </div>
        </div>
      </div>

      <div>
        <p className="analytics-panel__label">Word Growth</p>
        <MiniLineChart
          color="#5fa8ff"
          formatter={(value) => `${formatMetric(value)} words`}
          metricKey="word_count"
          points={timeline}
        />
      </div>

      <div>
        <p className="analytics-panel__label">Readability Trend</p>
        <MiniLineChart
          color="#4ec9b0"
          formatter={(value) => `${formatMetric(value, 1)} score`}
          metricKey="readability_score"
          points={timeline}
        />
      </div>

      <div>
        <p className="analytics-panel__label">Recent Versions</p>
        <div className="analytics-list-card">
          {timeline.slice(-6).reverse().map((point) => (
            <div key={point.version_number} className="analytics-version-row">
              <div>
                <strong>{`Version ${point.version_number}`}</strong>
                <div className="analytics-version-row__meta">{formatDate(point.created_at)}</div>
              </div>
              <div className="analytics-version-row__stats">
                <span>{`${formatMetric(point.word_count)} words`}</span>
                <span>{`${formatMetric(point.char_count)} chars`}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function deltaLabel(delta) {
  const sign = delta.delta > 0 ? "+" : "";
  return `${sign}${formatMetric(delta.delta, 2)}`;
}

function ComparePanel({ compare }) {
  const { comparison, error, isLoading, selectedVersions, setSelectedVersions, versions } = compare;

  if (isLoading && !versions.length) {
    return <Placeholder>Loading version history...</Placeholder>;
  }

  if (error && !versions.length) {
    return <Placeholder>Compare error: {error}</Placeholder>;
  }

  if (versions.length < 2) {
    return <Placeholder>Save at least two versions to compare revisions.</Placeholder>;
  }

  return (
    <div className="analytics-panel__stack">
      <div>
        <p className="analytics-panel__label">Version Selection</p>
        <div className="analytics-select-grid">
          <label className="analytics-select-card">
            <span>Base version</span>
            <select
              value={selectedVersions.versionA}
              onChange={(event) =>
                setSelectedVersions((current) => ({
                  ...current,
                  versionA: Number(event.target.value)
                }))
              }
            >
              {versions.map((version) => (
                <option key={`base-${version.version_number}`} value={version.version_number}>
                  {`Version ${version.version_number}`}
                </option>
              ))}
            </select>
          </label>
          <label className="analytics-select-card">
            <span>Target version</span>
            <select
              value={selectedVersions.versionB}
              onChange={(event) =>
                setSelectedVersions((current) => ({
                  ...current,
                  versionB: Number(event.target.value)
                }))
              }
            >
              {versions.map((version) => (
                <option key={`target-${version.version_number}`} value={version.version_number}>
                  {`Version ${version.version_number}`}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {isLoading && comparison ? <Placeholder>Refreshing comparison...</Placeholder> : null}
      {error && comparison ? <Placeholder>Compare error: {error}</Placeholder> : null}

      {comparison ? (
        <>
          <div className="analytics-metrics-grid">
            <MetricCard label="Changes" value={comparison.summary.total_changes} />
            <MetricCard label="Insertions" value={comparison.summary.insertions} />
            <MetricCard label="Deletions" value={comparison.summary.deletions} />
            <MetricCard label="Word Delta" value={comparison.summary.word_delta} />
          </div>

          <div>
            <p className="analytics-panel__label">Analytics Deltas</p>
            {comparison.analytics_deltas?.length ? (
              <div className="analytics-list-card">
                {comparison.analytics_deltas.map((delta) => (
                  <div key={delta.metric} className="analytics-delta-row">
                    <div>
                      <strong>{delta.metric.replaceAll("_", " ")}</strong>
                      <div className="analytics-version-row__meta">
                        {`${formatMetric(delta.old_value, 2)} -> ${formatMetric(delta.new_value, 2)}`}
                      </div>
                    </div>
                    <span className={`analytics-delta-row__badge is-${delta.direction}`}>
                      {deltaLabel(delta)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <Placeholder>No analytics deltas available for this comparison.</Placeholder>
            )}
          </div>

          <div>
            <p className="analytics-panel__label">Word-Level Diff</p>
            <div className="analytics-diff-card">
              {comparison.diff_chunks?.length ? (
                comparison.diff_chunks.map((chunk, index) => (
                  <span
                    key={`${chunk.operation}-${index}`}
                    className={`analytics-diff-chunk analytics-diff-chunk--${chunk.operation}`}
                  >
                    {chunk.text}
                  </span>
                ))
              ) : (
                <p className="analytics-diff-card__empty">No textual diff available.</p>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function AnalyticsSidebar({
  activeTab,
  analytics,
  compare,
  insights,
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
          <p className="analytics-sidebar__subtitle">See what changed, how it reads, and where the draft is heading.</p>
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
        {activeTab === "insights" ? <InsightsPanel insights={insights} /> : null}
        {activeTab === "compare" ? <ComparePanel compare={compare} /> : null}
      </section>
    </aside>
  );
}
