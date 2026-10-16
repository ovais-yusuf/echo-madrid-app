import type { Metadata } from "next";
import {
  getStandings,
  formatUpdatedAt,
  legacySiteUrl,
  type StandingsResponse,
} from "@/lib/api";
import { StandingsTable } from "@/components/standings-table";
import { RefreshButton } from "@/components/refresh-button";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "La Liga standings" };

export default async function StandingsPage() {
  let data: StandingsResponse | null = null;
  try {
    data = await getStandings();
  } catch {
    /* Render a recoverable state without leaking upstream details. */
  }
  const rows = data?.standings ?? [];
  const madrid = rows.find((row) => row.is_real_madrid);
  const updatedAt = formatUpdatedAt(data?.updated_at ?? null);
  const season = data?.season?.year_label;
  const goalDifference = madrid
    ? madrid.goals_for - madrid.goals_against
    : null;

  return (
    <div className="page-container">
      <section className="page-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="gold-line" />
            SPAIN / LA LIGA
          </div>
          <h1 id="page-title">
            Every point.
            <br />
            <span>Every position.</span>
          </h1>
          <p>
            La Liga standings, with Madrid in focus.
            <br className="desktop-break" /> The latest table stored in our
            database.
          </p>
        </div>
        <div className="hero-mark" aria-hidden="true">
          <span className="hero-number">LL</span>
          <span>LEAGUE STANDINGS</span>
        </div>
      </section>
      <div className="snapshot-bar">
        <div>
          <span className="snapshot-label">DATABASE SNAPSHOT</span>
          {season && <span className="season-label">Season {season}</span>}
        </div>
        <span>
          {updatedAt ? (
            <>
              Updated{" "}
              <time dateTime={data?.updated_at ?? undefined}>{updatedAt}</time>
            </>
          ) : (
            "Update time unavailable"
          )}
        </span>
      </div>
      {data === null ? (
        <section className="state-card" role="alert">
          <span className="eyebrow">TABLE UNAVAILABLE</span>
          <h2>We couldn’t load the standings.</h2>
          <p>
            The data service is unavailable right now. Try again in a moment.
          </p>
          <RefreshButton label="Try again" />
        </section>
      ) : rows.length === 0 ? (
        <section className="state-card">
          <span className="eyebrow">NO TABLE YET</span>
          <h2>The standings aren’t available yet.</h2>
          <p>
            There are no La Liga standings in the database. They will appear
            here after the next successful data import.
          </p>
          <RefreshButton />
        </section>
      ) : (
        <>
          <section
            className="summary-grid"
            aria-label="Real Madrid season summary"
          >
            <div className="summary-intro">
              <span className="eyebrow">OUR CLUB, AT A GLANCE</span>
              <h2>Real Madrid</h2>
              <span className="summary-context">
                {season ? `${season} · La Liga` : "La Liga"}
              </span>
            </div>
            <div className="summary-stat">
              <span>League position</span>
              <strong>
                {madrid ? (
                  <>
                    {String(madrid.position).padStart(2, "0")}
                    <small> / {rows.length}</small>
                  </>
                ) : (
                  "N/A"
                )}
              </strong>
            </div>
            <div className="summary-stat">
              <span>Total points</span>
              <strong>
                {madrid?.points ?? "N/A"}
                <small>{madrid ? ` / ${madrid.played} played` : ""}</small>
              </strong>
            </div>
            <div className="summary-stat">
              <span>Goal difference</span>
              <strong>
                {goalDifference === null
                  ? "N/A"
                  : `${goalDifference > 0 ? "+" : ""}${goalDifference}`}
                <small>
                  {madrid
                    ? `${madrid.goals_for} for · ${madrid.goals_against} against`
                    : ""}
                </small>
              </strong>
            </div>
          </section>
          {!madrid && (
            <p className="missing-note">
              Real Madrid has no row in this snapshot. Club summary values are
              unavailable.
            </p>
          )}
          <StandingsTable rows={rows} season={season || "Season unavailable"} />
          <div className="below-table">
            <aside className="data-note">
              <span className="note-icon" aria-hidden="true">
                i
              </span>
              <div>
                <h3>A table you can trace.</h3>
                <p>
                  Every number comes from our football-data.org imports. This is
                  a stored snapshot, not a live match feed. Free-tier updates
                  may be delayed.
                </p>
              </div>
            </aside>
            <a className="ask-card" href={`${legacySiteUrl()}/#question`}>
              <span>
                <span className="eyebrow">GO BEYOND THE TABLE</span>
                <strong>Got a Madrid question?</strong>
                <span>Ask Echo, answers from the data.</span>
              </span>
              <span className="ask-arrow" aria-hidden="true">
                ↗
              </span>
            </a>
          </div>
        </>
      )}
    </div>
  );
}
