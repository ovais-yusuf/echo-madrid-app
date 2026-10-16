import type { Metadata } from "next";
import Link from "next/link";
import {
  getStandings,
  getMatches,
  formatUpdatedAt,
  legacySiteUrl,
  type StandingsResponse,
  type MatchesResponse,
  type MatchCard,
} from "@/lib/api";
import { ClubCrest } from "@/components/club-crest";
import { RefreshButton } from "@/components/refresh-button";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Real Madrid, in focus" };

function fmtDateTime(iso: string): { date: string; time: string | null } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: "Date unavailable", time: null };
  const date = new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(d);
  return { date, time };
}

function outcomeOf(
  m: MatchCard,
  madridId: number | null,
): "win" | "draw" | "loss" | null {
  if (madridId === null || m.home_score === null || m.away_score === null)
    return null;
  const homeIsMadrid = m.home_team.id === madridId;
  const mine = homeIsMadrid ? m.home_score : m.away_score;
  const theirs = homeIsMadrid ? m.away_score : m.home_score;
  return mine > theirs ? "win" : mine < theirs ? "loss" : "draw";
}

function Matchup({
  m,
  madridId,
  showScore,
}: {
  m: MatchCard;
  madridId: number | null;
  showScore: boolean;
}) {
  const homeIsMadrid = madridId !== null && m.home_team.id === madridId;
  const awayIsMadrid = madridId !== null && m.away_team.id === madridId;
  const hasScore = m.home_score !== null && m.away_score !== null;
  return (
    <div className="home-matchup">
      <div className="home-team">
        <ClubCrest team={m.home_team} size={34} />
        <span className={homeIsMadrid ? "madrid-name" : ""}>
          {m.home_team.short_name || m.home_team.name}
        </span>
      </div>
      <div className="home-vs">
        {showScore && hasScore ? (
          <strong className="home-score">
            {m.home_score}
            <span>:</span>
            {m.away_score}
          </strong>
        ) : (
          <span className="home-versus">vs</span>
        )}
      </div>
      <div className="home-team">
        <ClubCrest team={m.away_team} size={34} />
        <span className={awayIsMadrid ? "madrid-name" : ""}>
          {m.away_team.short_name || m.away_team.name}
        </span>
      </div>
    </div>
  );
}

export default async function HomePage() {
  let standings: StandingsResponse | null = null;
  let upcoming: MatchesResponse | null = null;
  let results: MatchesResponse | null = null;

  const [s, u, r] = await Promise.allSettled([
    getStandings(),
    getMatches(new URLSearchParams({ view: "upcoming", limit: "1" })),
    getMatches(new URLSearchParams({ view: "results", limit: "1" })),
  ]);
  if (s.status === "fulfilled") standings = s.value;
  if (u.status === "fulfilled") upcoming = u.value;
  if (r.status === "fulfilled") results = r.value;

  const rows = standings?.standings ?? [];
  const madridRow = rows.find((row) => row.is_real_madrid) ?? null;
  const season = standings?.season?.year_label;
  const madridId = upcoming?.team?.id ?? results?.team?.id ?? null;
  const nextMatch = upcoming?.matches[0] ?? null;
  const lastMatch = results?.matches[0] ?? null;
  const importedAt = formatUpdatedAt(
    upcoming?.imported_at ?? results?.imported_at ?? null,
  );
  const allDown = standings === null && upcoming === null && results === null;
  const lastOutcome = lastMatch ? outcomeOf(lastMatch, madridId) : null;
  const askHref = `${legacySiteUrl()}/#question`;

  return (
    <div className="page-container">
      <section className="page-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="gold-line" />
            REAL MADRID / ECHO MADRID
          </div>
          <h1 id="page-title">
            The game,
            <br />
            <span>in focus.</span>
          </h1>
          <p>
            Standings, fixtures, and results for Real Madrid, grounded in stored
            football data.
            <br className="desktop-break" /> No guesses, no invented numbers.
          </p>
        </div>
        <div className="hero-mark" aria-hidden="true">
          <span className="hero-number">RM</span>
          <span>IN FOCUS</span>
        </div>
      </section>

      <div className="snapshot-bar">
        <div>
          <span className="snapshot-label">DATABASE SNAPSHOT</span>
          {season && <span className="season-label">Season {season}</span>}
        </div>
        <span>
          {importedAt ? (
            <>
              Imported{" "}
              <time dateTime={upcoming?.imported_at ?? results?.imported_at ?? undefined}>
                {importedAt}
              </time>
            </>
          ) : (
            "Import time unavailable"
          )}
        </span>
      </div>

      {allDown ? (
        <section className="state-card" role="alert">
          <span className="eyebrow">SNAPSHOT UNAVAILABLE</span>
          <h2>We could not load the snapshot.</h2>
          <p>The data service is unavailable right now. Try again in a moment.</p>
          <RefreshButton label="Try again" />
        </section>
      ) : (
        <>
          <section className="home-snapshot" aria-label="Real Madrid right now">
            <article className="home-card">
              <span className="eyebrow">LEAGUE POSITION</span>
              {standings === null ? (
                <p className="home-empty">The standings are unavailable right now.</p>
              ) : madridRow ? (
                <>
                  <strong className="home-stat">
                    {String(madridRow.position).padStart(2, "0")}
                    <small> / {rows.length}</small>
                  </strong>
                  <span className="home-sub">
                    {madridRow.points} pts · {madridRow.played} played ·{" "}
                    {madridRow.won}W {madridRow.drawn}D {madridRow.lost}L
                  </span>
                  <span className="home-context">
                    {season ? `${season} · La Liga` : "La Liga"}
                  </span>
                  <Link className="home-link" href="/standings">
                    Full table <span aria-hidden="true">→</span>
                  </Link>
                </>
              ) : (
                <p className="home-empty">
                  Real Madrid has no row in the current table snapshot.
                </p>
              )}
            </article>

            <article className="home-card">
              <span className="eyebrow">NEXT FIXTURE</span>
              {upcoming === null ? (
                <p className="home-empty">Fixtures are unavailable right now.</p>
              ) : nextMatch ? (
                <>
                  <span className="home-comp">{nextMatch.competition.name}</span>
                  <Matchup m={nextMatch} madridId={madridId} showScore={false} />
                  <span className="home-sub">
                    {(() => {
                      const { date, time } = fmtDateTime(nextMatch.utc_date);
                      return nextMatch.status === "SCHEDULED"
                        ? `${date} · Kick-off not confirmed`
                        : `${date} · ${time} UTC`;
                    })()}
                  </span>
                  <Link className="home-link" href="/matches">
                    All fixtures <span aria-hidden="true">→</span>
                  </Link>
                </>
              ) : (
                <p className="home-empty">No upcoming fixtures have been imported.</p>
              )}
            </article>

            <article className="home-card">
              <span className="eyebrow">LAST RESULT</span>
              {results === null ? (
                <p className="home-empty">Results are unavailable right now.</p>
              ) : lastMatch ? (
                <>
                  <span className="home-comp">{lastMatch.competition.name}</span>
                  <Matchup m={lastMatch} madridId={madridId} showScore={true} />
                  <span
                    className={`home-badge ${lastOutcome ? `outcome-${lastOutcome}` : ""}`}
                  >
                    {lastOutcome
                      ? `Madrid ${lastOutcome === "win" ? "won" : lastOutcome === "loss" ? "lost" : "drew"}`
                      : "Score unavailable"}
                  </span>
                  <span className="home-sub">
                    {fmtDateTime(lastMatch.utc_date).date} · Full time
                  </span>
                  <Link className="home-link" href="/matches?view=results">
                    All results <span aria-hidden="true">→</span>
                  </Link>
                </>
              ) : (
                <p className="home-empty">No results have been imported yet.</p>
              )}
            </article>
          </section>

          <div className="below-table">
            <aside className="data-note">
              <span className="note-icon" aria-hidden="true">
                i
              </span>
              <div>
                <h3>Everything here is stored data.</h3>
                <p>
                  Every figure comes from our football-data.org imports. This is a
                  stored snapshot, not a live match feed. Free-tier updates may be
                  delayed.
                </p>
              </div>
            </aside>
            <a className="ask-card" href={askHref}>
              <span>
                <span className="eyebrow">GO BEYOND THE SNAPSHOT</span>
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
