import Link from "next/link";
import { getData, type Matchday, type MatchCard, type Preview, type RecordData } from "@/lib/api";
import { LocalKickoff, ShareCard } from "./match-tools";
const labels: Record<string, string> = {SCHEDULED: "Scheduled · time unconfirmed", TIMED: "Scheduled", IN_PLAY: "In play · delayed feed", PAUSED: "Halftime · delayed feed", FINISHED: "Finished", POSTPONED: "Postponed", CANCELLED: "Cancelled", SUSPENDED: "Suspended", EXTRA_TIME: "Extra time", PENALTY_SHOOTOUT: "Penalty shootout", AWARDED: "Awarded"};
export function FixtureCard({match, label, updated}: {match: MatchCard; label: string; updated: string | null}) {
  const score = match.home_score !== null && match.away_score !== null ? `${match.home_score}–${match.away_score}` : "vs";
  return <article className="home-card matchday-card"><span className="eyebrow">{label}</span><h3>{match.home_team.name} {score} {match.away_team.name}</h3>
    <strong>{labels[match.status] || match.status}</strong><p>{match.competition.name} · {match.season.year_label}</p><LocalKickoff match={match}/>
    {match.status === "FINISHED" && <p>Score recap: {score === "vs" ? "Final score unavailable." : `${match.home_team.name} ${score} ${match.away_team.name}.`} Player events, possession and tactical explanations are unavailable.</p>}
    {!["FINISHED", "AWARDED"].includes(match.status) && <a className="home-link" href={`/calendar/${match.id}`}>Download calendar event</a>}
    <ShareCard title={match.status === "FINISHED" ? "FULL TIME" : "MATCHDAY"} lines={[match.home_team.name, score, match.away_team.name, labels[match.status] || match.status, match.competition.name, match.utc_date]} updated={updated}/>
  </article>;
}
export function RecordSummary({data}: {data: RecordData}) {
  if (!data.available) return <p>{data.team}: {data.reason || "No completed matches with scores available."}</p>;
  return <article className="home-card"><h3>{data.team} · {data.venue}</h3><strong>{data.form_oldest_first.join(" · ")} <small>(oldest first)</small></strong>
    <p>{data.count} matches · {data.won}W {data.drawn}D {data.lost}L</p><p>{data.goals_for} scored · {data.goals_against} conceded · {data.clean_sheets} clean sheets</p>
    <p>{data.period_start?.slice(0,10)} to {data.period_end?.slice(0,10)}</p><small>{data.freshness.message} Imported: {data.freshness.last_success || "unknown"}</small></article>;
}
export async function MatchdayPanel({compact = false}: {compact?: boolean}) {
  let data: Matchday;
  try { data = await getData<Matchday>("/matchday"); } catch { return <section className="state-card">Matchday data is temporarily unavailable.</section>; }
  if (compact) return <section className="team-block"><h2>Matchday centre</h2>{data.current && <FixtureCard match={data.current} label="CURRENT MATCH" updated={data.freshness.last_success}/>}<Link className="home-link" href="/matchday">Match status, opponent preview and share cards →</Link>{data.unresolved.length > 0 && <p className="stale-data">{data.unresolved.length} recent fixtures have unresolved, postponed or cancelled statuses. Check the matchday centre.</p>}</section>;
  let preview: Preview | null = null;
  try { preview = await getData<Preview>("/preview"); } catch { /* explicit unavailable below */ }
  return <><p className={data.freshness.stale ? "stale-data" : ""}>{data.freshness.message}</p><div className="matchday-grid">
    {data.current && <FixtureCard match={data.current} label="CURRENT MATCH" updated={data.freshness.last_success}/>}
    {data.next && <FixtureCard match={data.next} label="NEXT FIXTURE" updated={data.freshness.last_success}/>}
    {data.latest && <FixtureCard match={data.latest} label="LATEST RESULT" updated={data.freshness.last_success}/>}
    {!data.current && !data.next && !data.latest && <p>No matches imported yet.</p>}
  </div>{data.unresolved.length > 0 && <section className="team-block"><h2>Awaiting resolution</h2><p>Kickoff has passed, but no finished result is stored. We do not infer that a match is in play or completed.</p><div className="matchday-grid">{data.unresolved.map(m => <FixtureCard key={m.id} match={m} label="PROVIDER STATUS" updated={data.freshness.last_success}/>)}</div></section>}
    <section className="team-block"><h2>Opponent preview</h2>{preview?.available ? <><p>Latest five covered completed matches per sample. Home/away samples are selected separately; coverage may be incomplete.</p><div className="matchday-grid">{[preview.madrid, preview.opponent, preview.madrid_venue, preview.opponent_venue].map((r,i) => <RecordSummary data={r} key={i}/>)}</div><h3>Previous meetings in our database</h3>{preview.previous_meetings.length ? preview.previous_meetings.map(m => <p key={m.id}>{m.utc_date.slice(0,10)} · {m.home_team.name} {m.home_score ?? "—"}–{m.away_score ?? "—"} {m.away_team.name}</p>) : <p>No previous meetings available.</p>}</> : <p>{preview?.reason || "Opponent history is unavailable."}</p>}</section>
  </>;
}
