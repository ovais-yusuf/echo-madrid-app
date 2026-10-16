import type { Metadata } from "next";
import Link from "next/link";
import {
  getMatches,
  formatUpdatedAt,
  legacySiteUrl,
  type MatchesResponse,
  type MatchCard,
} from "@/lib/api";
import { ClubCrest } from "@/components/club-crest";
import { RefreshButton } from "@/components/refresh-button";

export const metadata: Metadata = { title: "Matches & fixtures" };
export const dynamic = "force-dynamic";
type Search = Record<string, string | string[] | undefined>;
const pageSize = 12;
const first = (value: string | string[] | undefined) =>
  Array.isArray(value) ? value[0] : value;
const validFilter = (value: string | undefined) =>
  value && value.length <= 20 ? value : undefined;

function matchDate(value: string) {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(date),
    time: new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    }).format(date),
  };
}

function MatchItem({
  match,
  madridId,
}: {
  match: MatchCard;
  madridId: number;
}) {
  const date = matchDate(match.utc_date);
  const finished = match.status === "FINISHED";
  const hasScore = match.home_score !== null && match.away_score !== null;
  const scored =
    hasScore && (finished || ["IN_PLAY", "PAUSED"].includes(match.status));
  const homeIsMadrid = match.home_team.id === madridId;
  const madridScore = homeIsMadrid ? match.home_score : match.away_score;
  const opponentScore = homeIsMadrid ? match.away_score : match.home_score;
  const outcome =
    finished && madridScore !== null && opponentScore !== null
      ? madridScore > opponentScore
        ? "win"
        : madridScore < opponentScore
          ? "loss"
          : "draw"
      : null;
  const statusLabels: Record<string, string> = {
    SCHEDULED: "Scheduled",
    TIMED: "Kick-off confirmed",
    FINISHED: "Full time",
    IN_PLAY: "In play (stored)",
    PAUSED: "Paused (stored)",
    POSTPONED: "Postponed",
    SUSPENDED: "Suspended",
    CANCELED: "Cancelled",
    CANCELLED: "Cancelled",
    AWARDED: "Awarded",
  };
  return (
    <article
      className={`match-card ${outcome ? `match-${outcome}` : ""}`}
      aria-label={`${match.home_team.name} versus ${match.away_team.name}, ${date.date}`}
    >
      <div className="match-card-top">
        <span>{match.competition.name}</span>
        <span>
          {match.season.year_label}
          {match.matchday !== null ? ` · Matchday ${match.matchday}` : ""}
        </span>
      </div>
      <div className="match-card-body">
        <div className="match-club">
          <ClubCrest team={match.home_team} size={42} />
          <span className={homeIsMadrid ? "madrid-name" : ""}>
            {match.home_team.short_name || match.home_team.name}
          </span>
          <small>HOME</small>
        </div>
        <div className="match-center">
          {scored ? (
            <strong className="match-score">
              {match.home_score}
              <span>:</span>
              {match.away_score}
            </strong>
          ) : (
            <strong className="match-versus">vs</strong>
          )}
          <span
            className={`match-status ${outcome ? `outcome-${outcome}` : ""}`}
          >
            {outcome
              ? `Madrid ${outcome === "win" ? "won" : outcome === "loss" ? "lost" : "drew"}`
              : statusLabels[match.status] ||
                match.status.replaceAll("_", " ").toLowerCase()}
          </span>
          {finished && !hasScore && <small>Score unavailable</small>}
        </div>
        <div className="match-club">
          <ClubCrest team={match.away_team} size={42} />
          <span className={!homeIsMadrid ? "madrid-name" : ""}>
            {match.away_team.short_name || match.away_team.name}
          </span>
          <small>AWAY</small>
        </div>
      </div>
      <div className="match-card-bottom">
        <time dateTime={match.utc_date}>{date.date}</time>
        <span>
          {match.status === "SCHEDULED"
            ? "Kick-off not confirmed"
            : `${date.time} UTC`}
          {finished ? " · Full time" : ""}
        </span>
      </div>
    </article>
  );
}

export default async function MatchesPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const search = await searchParams;
  const rawView = first(search.view);
  const view =
    rawView === "results" || rawView === "all" ? rawView : "upcoming";
  const competition = validFilter(first(search.competition));
  const season = validFilter(first(search.season));
  const rawPage = Number(first(search.page) || "1");
  const page =
    Number.isSafeInteger(rawPage) && rawPage > 0 && rawPage <= 100000
      ? rawPage
      : 1;
  const query = new URLSearchParams({
    view,
    limit: String(pageSize),
    offset: String((page - 1) * pageSize),
  });
  if (competition) query.set("competition", competition);
  if (season) query.set("season", season);
  let data: MatchesResponse | null = null;
  try {
    data = await getMatches(query);
  } catch {
    /* Only display the recoverable state, never upstream internals. */
  }
  const selectedSeason = season || data?.selected_season || "all";
  function href(nextView = view, nextPage = 1, clearFilters = false) {
    const params = new URLSearchParams({ view: nextView });
    if (!clearFilters) {
      if (competition) params.set("competition", competition);
      if (selectedSeason) params.set("season", selectedSeason);
    }
    if (nextPage > 1) params.set("page", String(nextPage));
    return `/matches?${params}`;
  }
  const importedAt = formatUpdatedAt(data?.imported_at ?? null);
  return (
    <div className="page-container">
      <section className="page-hero" aria-labelledby="matches-title">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="gold-line" />
            REAL MADRID / MATCH CENTRE
          </div>
          <h1 id="matches-title">
            The next chapter.
            <br />
            <span>The last whistle.</span>
          </h1>
          <p>
            Upcoming fixtures and past results.
            <br className="desktop-break" />
            Every match, grounded in our stored data.
          </p>
        </div>
        <div className="hero-mark" aria-hidden="true">
          <span className="hero-number">90′</span>
          <span>MATCHES & FIXTURES</span>
        </div>
      </section>
      <div className="snapshot-bar">
        <div>
          <span className="snapshot-label">DATABASE SNAPSHOT</span>
          <span className="season-label">
            {selectedSeason === "all"
              ? "All stored seasons"
              : `Season ${selectedSeason}`}
          </span>
        </div>
        <span>
          {importedAt ? (
            <>
              Last match import{" "}
              <time dateTime={data?.imported_at ?? undefined}>
                {importedAt}
              </time>
            </>
          ) : (
            "Match import time unavailable"
          )}
        </span>
      </div>
      <section className="matches-section" aria-labelledby="matches-heading">
        <div className="matches-heading">
          <div>
            <span className="eyebrow">THE SCHEDULE, IN FOCUS</span>
            <h2 id="matches-heading">Matches & fixtures</h2>
          </div>
          <RefreshButton label="Refresh matches" />
        </div>
        <nav className="match-tabs" aria-label="Match views">
          {[
            { value: "upcoming", label: "Upcoming" },
            { value: "results", label: "Results" },
            { value: "all", label: "All matches" },
          ].map((tab) => (
            <Link
              key={tab.value}
              href={href(tab.value)}
              className={view === tab.value ? "match-tab active" : "match-tab"}
              aria-current={view === tab.value ? "page" : undefined}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        {data === null ? (
          <section className="state-card" role="alert">
            <span className="eyebrow">MATCHES UNAVAILABLE</span>
            <h2>We couldn’t load the matches.</h2>
            <p>
              The data service is unavailable right now. Try again in a moment.
            </p>
            <RefreshButton label="Try again" />
          </section>
        ) : (
          <>
            <form action="/matches" method="get" className="match-filters">
              <input type="hidden" name="view" value={view} />
              <label>
                Competition
                <select
                  name="competition"
                  defaultValue={competition || ""}
                  key={`competition-${competition}`}
                >
                  <option value="">All competitions</option>
                  {competition &&
                    !data.competitions.some(
                      (item) => item.code === competition,
                    ) && (
                      <option value={competition}>
                        Unavailable ({competition})
                      </option>
                    )}
                  {data.competitions
                    .filter((item) => item.code)
                    .map((item) => (
                      <option key={item.id} value={item.code!}>
                        {item.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Season
                <select
                  name="season"
                  defaultValue={selectedSeason}
                  key={`season-${selectedSeason}`}
                >
                  <option value="all">All stored seasons</option>
                  {selectedSeason !== "all" &&
                    !data.seasons.includes(selectedSeason) && (
                      <option value={selectedSeason}>
                        Unavailable ({selectedSeason})
                      </option>
                    )}
                  {data.seasons.map((label) => (
                    <option key={label} value={label}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="filter-submit">
                Apply filters
              </button>
              <Link className="filter-reset" href={href(view, 1, true)}>
                Reset
              </Link>
            </form>
            {data.matches.length > 0 && data.team ? (
              <>
                <div className="match-count">
                  <span>
                    {view === "upcoming"
                      ? "Nearest fixtures first"
                      : "Newest matches first"}
                  </span>
                  <span>
                    {data.offset + 1}–{data.offset + data.matches.length} of{" "}
                    {data.total} matches
                  </span>
                </div>
                <div className="match-grid">
                  {data.matches.map((match) => (
                    <MatchItem
                      key={match.id}
                      match={match}
                      madridId={data.team!.id}
                    />
                  ))}
                </div>
              </>
            ) : (
              <div className="state-card">
                <span className="eyebrow">NO MATCHES TO SHOW</span>
                <h2>
                  {!data.team
                    ? "Madrid’s match data isn’t available yet."
                    : page > 1
                      ? "There are no matches on this page."
                      : view === "upcoming"
                        ? "No upcoming fixtures in this view."
                        : view === "results"
                          ? "No completed results in this view."
                          : "No stored matches in this view."}
                </h2>
                <p>
                  {page > 1
                    ? "Return to the first page or change your filters."
                    : "Try a different season, competition, or match view. Only matches already imported into the database appear here."}
                </p>
                <Link className="text-link" href={href("all", 1, true)}>
                  Browse all matches →
                </Link>
              </div>
            )}
            {(page > 1 || data.has_more) && (
              <nav className="match-pagination" aria-label="Match pages">
                {page > 1 ? (
                  <Link href={href(view, page - 1)} className="refresh-button">
                    ← Previous
                  </Link>
                ) : (
                  <span />
                )}
                <span>Page {page}</span>
                {data.has_more ? (
                  <Link href={href(view, page + 1)} className="refresh-button">
                    Next →
                  </Link>
                ) : (
                  <span />
                )}
              </nav>
            )}
          </>
        )}
      </section>
      <div className="below-table">
        <aside className="data-note">
          <span className="note-icon" aria-hidden="true">
            i
          </span>
          <div>
            <h3>Stored data. Clear limits.</h3>
            <p>
              All times are in UTC. Statuses and scores reflect our last
              imports, not a live match feed. Free-tier data may be delayed.
              Upcoming includes future scheduled fixtures; postponed and other
              statuses remain under All matches.
            </p>
          </div>
        </aside>
        <a className="ask-card" href={`${legacySiteUrl()}/#question`}>
          <span>
            <span className="eyebrow">ASK ABOUT THE GAME</span>
            <strong>Let the data answer.</strong>
            <span>Ask Echo about Madrid’s matches.</span>
          </span>
          <span className="ask-arrow" aria-hidden="true">
            ↗
          </span>
        </a>
      </div>
    </div>
  );
}
