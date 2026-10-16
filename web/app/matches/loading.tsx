export default function Loading() {
  return (
    <div className="page-container">
      <section className="state-card" role="status">
        <span className="eyebrow">REAL MADRID</span>
        <h1>Loading the matches…</h1>
        <p>Getting fixtures and results from our database.</p>
        <div className="loading-lines" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </section>
    </div>
  );
}
