export default function Loading() {
  return (
    <div className="page-container">
      <section className="state-card" role="status">
        <span className="eyebrow">LA LIGA</span>
        <h1>Loading the table…</h1>
        <p>Getting the latest stored standings.</p>
        <div className="loading-lines" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>
      </section>
    </div>
  );
}
