import { getData, type RecordData } from "@/lib/api";
import { RecordSummary } from "./matchday-panel";
import { ShareCard } from "./match-tools";
export async function SeasonAnalysis() {
  const results = await Promise.allSettled(["all", "home", "away"].map(venue => getData<RecordData>(`/analytics?venue=${venue}`)));
  const records = results.flatMap(r => r.status === "fulfilled" && r.value.available ? [r.value] : []);
  const overall = records.find(r => r.venue === "all");
  if (!overall) return <section className="team-block"><h2>Season analysis</h2><p>Completed match data is unavailable.</p></section>;
  const max = Math.max(1,...overall.progress.map(p => Math.max(p.goals_for,p.goals_against)));
  return <section className="team-block"><h2>Season in numbers</h2><p>{overall.scope}</p><p>{overall.clean_sheets} clean sheets in {overall.count} covered completed matches.</p><div className="matchday-grid">{records.filter(r => r.venue !== "all").map(r => <RecordSummary key={r.venue} data={r}/>)}</div>
    <h3>Scoring trend</h3><p>Gold: scored · Navy: conceded. Each row is one covered completed match, oldest first.</p>
    <div className="trend-chart" role="img" aria-label="Goals scored and conceded by match; exact values follow each bar">{overall.progress.map((p,i) => <div className="trend-row" key={i}><span>{p.date.slice(0,10)}</span><div><div className="trend-for" style={{width:`${p.goals_for/max*100}%`}}/><div className="trend-against" style={{width:`${p.goals_against/max*100}%`}}/></div><span>{p.goals_for} / {p.goals_against}</span></div>)}</div>
    <h3>Season progress</h3><p>Cumulative result points across this sample; not official league points.</p><svg viewBox="0 0 620 200" role="img" aria-label="Cumulative result points across the covered season sample" style={{width:"100%",maxHeight:240}}><line x1="10" y1="180" x2="610" y2="180" stroke="#d3d6dc"/><polyline fill="none" stroke="#c9a85d" strokeWidth="4" points={overall.progress.map((p,i) => `${10+i/Math.max(1,overall.progress.length-1)*600},${180-p.cumulative_result_points/Math.max(1,...overall.progress.map(v => v.cumulative_result_points))*160}`).join(" ")}/></svg><div className="table-scroll"><table><thead><tr><th>Date</th><th>Result points</th></tr></thead><tbody>{overall.progress.map((p,i) => <tr key={i}><td>{p.date.slice(0,10)}</td><td>{p.cumulative_result_points}</td></tr>)}</tbody></table></div>
    <ShareCard title="RECENT FORM" lines={[overall.team, overall.form_oldest_first.slice(-5).join(" · ") + " (oldest first)", `Latest ${Math.min(5, overall.count)} covered results`, overall.period_end?.slice(0,10) || "Date unavailable"]} updated={overall.freshness.last_success}/>
  </section>;
}
