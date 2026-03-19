const migrationSteps = [
  "Scaffold React + Vite and keep the legacy frontend as a fallback.",
  "Move the workspace shell, toolbar, and layout into React.",
  "Migrate the editor and preview flow.",
  "Port collaboration, versioning, export, and analytics in smaller slices."
];

export default function App() {
  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Collabscribe React Migration</p>
        <h1>React frontend scaffolded.</h1>
        <p className="lede">
          The new frontend is now bootstrapped with Vite. The existing HTML app
          remains the runtime fallback until feature parity is migrated.
        </p>
      </section>

      <section className="status-grid" aria-label="Migration status">
        <article className="status-card">
          <h2>Current serving behavior</h2>
          <p>
            FastAPI serves the React build if <code>frontend-app/dist</code>{" "}
            exists. Otherwise it keeps serving the legacy frontend.
          </p>
        </article>
        <article className="status-card">
          <h2>Why this step exists</h2>
          <p>
            It creates a safe migration seam so the UI can be rewritten and
            pushed to GitHub in reviewable increments.
          </p>
        </article>
      </section>

      <section className="plan-card">
        <h2>Planned migration slices</h2>
        <ol>
          {migrationSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>
    </main>
  );
}
