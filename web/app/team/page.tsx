import type { Metadata } from "next";
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
export const metadata: Metadata = { title: "Real Madrid, the club" };

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(d);
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

function TeamsLine({ m, madridId }: { m: MatchCard; madridId: number | null }) {
  const homeIsMadrid = madridId !== null && m.home_team.id === madridId;
  const awayIsMadrid = madridId !== null && m.away_team.id === madridId;
  return (
    <span className="tr-teams">
      <span className={homeIsMadrid ? "madrid-name" : ""}>
        {m.home_team.short_name || m.home_team.name}
      </span>
      <span className="tr-v"> v </span>
      <span className={awayIsMadrid ? "madrid-name" : ""}>
        {m.away_team.short_name || m.away_team.name}
      </span>
    </span>
  );
}

export default async function TeamPage() {
  let standings: StandingsResponse | null = null;
  let results: MatchesResponse | null = null;
  let upcoming: MatchesResponse | null = null;

  const [s, r, u] = await Promise.allSettled([
    getStandings(),
    getMatches(new URLSearchParams({ view: "results", limit: "5" })),
    getMatches(new URLSearchParams({ view: "upcoming", limit: "3" })),
  ]);
  if (s.status === "fulfilled") standings = s.value;
  if (r.status === "fulfilled") results = r.value;
  if (u.status === "fulfilled") upcoming = u.value;

  const rows = standings?.standings ?? [];
  const madridRow = rows.find((row) => row.is_real_madrid) ?? null;
  const club =
    results?.team ?? upcoming?.team ?? madridRow?.team ?? null;
  const madridId =
    results?.team?.id ?? upcoming?.team?.id ?? madridRow?.team.id ?? null;
  const season = standings?.season?.year_label;
  const competitions = results?.competitions ?? upcoming?.competitions ?? [];
  const recent = results?.matches ?? [];
  const fixtures = upcoming?.matches ?? [];
  const importedAt = formatUpdatedAt(
    results?.imported_at ?? upcoming?.imported_at ?? null,
  );
  const goalDifference: number | null = madridRow
    ? madridRow.goals_for - madridRow.goals_against
    : null;
  const allDown =
    standings === null && results === null && upcoming === null;

  return (
    <div className="page-container">
      <section className="page-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="gold-line" />
            THE CLUB
          </div>
          <h1 id="page-title">{club ? club.name : "Real Madrid"}</h1>
          <p>
            {club?.short_name ? `${club.short_name}. ` : ""}A profile built from
            the match and standings data stored in our database.
            <br className="desktop-break" /> Tracked via football-data.org.
          </p>
        </div>
        <div className="team-crest">
          {club ? (
            <ClubCrest team={club} size={104} />
          ) : (
            <span className="crest-fallback" style={{ width: 104, height: 104 }}>
              RM
            </span>
          )}
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
              <time
                dateTime={results?.imported_at ?? upcoming?.imported_at ?? undefined}
              >
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
          <span className="eyebrow">CLUB PROFILE UNAVAILABLE</span>
          <h2>We could not load the club profile.</h2>
          <p>The data service is unavailable right now. Try again in a moment.</p>
          <RefreshButton label="Try again" />
        </section>
      ) : (
        <>
          {madridRow ? (
            <section className="summary-grid" aria-label="Real Madrid season record">
              <div className="summary-intro">
                <span className="eyebrow">SEASON RECORD</span>
                <h2>Real Madrid</h2>
                <span className="summary-context">
                  {season ? `${season} · La Liga` : "La Liga"} ·{" "}
                  {madridRow.won}W {madridRow.drawn}D {madridRow.lost}L
                </span>
              </div>
              <div className="summary-stat">
                <span>League position</span>
                <strong>
                  {String(madridRow.position).padStart(2, "0")}
                  <small> / {rows.length}</small>
                </strong>
              </div>
              <div className="summary-stat">
                <span>Total points</span>
                <strong>
                  {madridRow.points}
                  <small> / {madridRow.played} played</small>
                </strong>
              </div>
              <div className="summary-stat">
                <span>Goal difference</span>
                <strong>
                  {goalDifference === null
                    ? "N/A"
                    : `${goalDifference > 0 ? "+" : ""}${goalDifference}`}
                  <small>
                    {madridRow
                      ? `${madridRow.goals_for} for · ${madridRow.goals_against} against`
                      : ""}
                  </small>
                </strong>
              </div>
            </section>
          ) : (
            <p className="missing-note">
              {standings === null
                ? "The standings are unavailable right now, so the season record cannot be shown."
                : "Real Madrid has no row in the current standings snapshot, so the season record is unavailable."}
            </p>
          )}

          <section className="team-block" aria-label="Recent form">
            <h2>Recent form</h2>
            {results === null ? (
              <p className="home-empty">Results are unavailable right now.</p>
            ) : recent.length === 0 ? (
              <p className="home-empty">No results have been imported yet.</p>
            ) : (
              <>
                <div className="team-form" aria-hidden="true">
                  {recent.map((m) => {
                    const o = outcomeOf(m, madridId);
                    return (
                      <span
                        key={`chip-${m.id}`}
                        className={`form-chip ${o ? `outcome-${o}` : ""}`}
                      >
                        {o ? o.charAt(0).toUpperCase() : "?"}
                      </span>
                    );
                  })}
                </div>
                <div className="team-list">
                  {recent.map((m) => {
                    const o = outcomeOf(m, madridId);
                    const hasScore =
                      m.home_score !== null && m.away_score !== null;
                    return (
                      <div className="team-row" key={m.id}>
                        <span className="tr-meta">
                          {fmtDate(m.utc_date)} · {m.competition.name}
                        </span>
                        <TeamsLine m={m} madridId={madridId} />
                        <span className="tr-result">
                          {hasScore ? (
                            <strong className="tr-score">
                              {m.home_score} : {m.away_score}
                            </strong>
                          ) : (
                            <span className="tr-meta">Score unavailable</span>
                          )}
                          <span
                            className={`home-badge ${o ? `outcome-${o}` : ""}`}
                          >
                            {o
                              ? o === "win"
                                ? "W"
                                : o === "loss"
                                  ? "L"
                                  : "D"
                              : "?"}
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </section>

          <section className="team-block" aria-label="Next fixtures">
            <h2>Next fixtures</h2>
            {upcoming === null ? (
              <p className="home-empty">Fixtures are unavailable right now.</p>
            ) : fixtures.length === 0 ? (
              <p className="home-empty">
                No upcoming fixtures have been imported.
              </p>
            ) : (
              <div className="team-list">
                {fixtures.map((m) => (
                  <div className="team-row" key={m.id}>
                    <span className="tr-meta">
                      {fmtDate(m.utc_date)} · {m.competition.name}
                    </span>
                    <TeamsLine m={m} madridId={madridId} />
                    <span className="tr-result">
                      <span className="tr-meta">
                        {m.status === "SCHEDULED"
                          ? "Kick-off not confirmed"
                          : `${fmtTime(m.utc_date)} UTC`}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {competitions.length > 0 && (
            <section className="team-block" aria-label="Competitions tracked">
              <h2>Competitions tracked</h2>
              <div className="team-chips">
                {competitions.map((c) => (
                  <span className="team-chip" key={c.id}>
                    {c.name}
                    {c.code ? ` · ${c.code}` : ""}
                  </span>
                ))}
              </div>
            </section>
          )}

          <div className="below-table">
            <aside className="data-note">
              <span className="note-icon" aria-hidden="true">
                i
              </span>
              <div>
                <h3>A club profile you can trace.</h3>
                <p>
                  Every figure here comes from our football-data.org imports of
                  Madrid matches and standings. There is no squad or player data
                  in the database, so none is shown. This is a stored snapshot,
                  not a live feed.
                </p>
              </div>
            </aside>
            <a className="ask-card" href={`${legacySiteUrl()}/#question`}>
              <span>
                <span className="eyebrow">ASK ABOUT THE CLUB</span>
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
