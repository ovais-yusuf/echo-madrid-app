import Link from "next/link";
export default function NotFound() {
  return (
    <div className="page-container">
      <section className="state-card">
        <span className="eyebrow">404</span>
        <h1>Page not found.</h1>
        <p>
          This page isn’t available. Explore the latest stored league table.
        </p>
        <Link href="/standings" className="text-link">
          Go to standings →
        </Link>
      </section>
    </div>
  );
}
