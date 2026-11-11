import { getData, type Freshness, formatUpdatedAt } from "@/lib/api";
export async function DataStatus() {
  try {
    const clocks = await getData<Record<string, Freshness>>("/freshness");
    return <aside className="freshness-strip" aria-label="Data freshness">
      <strong>football-data.org · Delayed data, not live scores</strong>
      {Object.entries(clocks).map(([key, clock]) => <span key={key} className={clock.stale ? "stale-data" : ""}>
        {key === "matches" ? "Matches" : key === "PD" ? "La Liga table" : "Champions League table"}: {formatUpdatedAt(clock.last_success) || "No successful import"}
        {clock.access_issue ? " · Provider access denied: check token and subscription coverage" : ""}{clock.stale ? " · STALE / UNAVAILABLE" : ""}{clock.last_attempt_status === "failed" ? " · Latest refresh failed; retaining previous data" : ""}
      </span>)}
    </aside>;
  } catch { return <aside className="freshness-strip stale-data">Data service unavailable. Freshness cannot be verified.</aside>; }
}
