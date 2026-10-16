"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="page-container">
      <section className="state-card" role="alert">
        <h1>Something went wrong.</h1>
        <p>Please try loading this page again.</p>
        <button className="refresh-button" onClick={reset}>
          Try again
        </button>
      </section>
    </div>
  );
}
