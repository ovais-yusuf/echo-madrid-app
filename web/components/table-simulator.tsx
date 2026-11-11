"use client";
import { useState } from "react";
import { simulateTable } from "@/lib/simulator";
import type { Standing } from "@/lib/api";
export function TableSimulator({rows}: {rows: Standing[]}) {
  const [home, setHome] = useState(String(rows[0]?.team.id || ""));
  const [away, setAway] = useState(String(rows[1]?.team.id || ""));
  const [hg, setHg] = useState(0); const [ag, setAg] = useState(0);
  const [applied, setApplied] = useState(false);
  const valid = home !== away && rows.some(r => String(r.team.id) === home) && rows.some(r => String(r.team.id) === away);
  const projected = applied && valid ? simulateTable(rows, Number(home), Number(away), hg, ag) : rows;
  const edit = () => setApplied(false);
  return <section className="team-block simulator"><span className="eyebrow">HYPOTHETICAL · NOT OFFICIAL</span><h2>What if?</h2><p>Add one imaginary match to the stored La Liga table. This does not alter official data or claim that the fixture is scheduled.</p>
    <p>Approximate sorting: points, overall goal difference, goals scored, then previous position. Official head-to-head and other tie-break rules are not applied. Qualification is not predicted.</p>
    <div className="card-actions"><label>Home club<select value={home} onChange={e => {setHome(e.target.value); edit();}}>{rows.map(r => <option key={r.team.id} value={r.team.id}>{r.team.name}</option>)}</select></label>
    <label>Home goals<input type="number" min="0" max="30" value={hg} onChange={e => {setHg(Math.min(30,Math.max(0,Math.trunc(Number(e.target.value))))); edit();}}/></label>
    <label>Away club<select value={away} onChange={e => {setAway(e.target.value); edit();}}>{rows.map(r => <option key={r.team.id} value={r.team.id}>{r.team.name}</option>)}</select></label>
    <label>Away goals<input type="number" min="0" max="30" value={ag} onChange={e => {setAg(Math.min(30,Math.max(0,Math.trunc(Number(e.target.value))))); edit();}}/></label></div>
    {!valid && <p role="status">Choose two different clubs.</p>}<div className="card-actions"><button className="refresh-button" disabled={!valid} onClick={() => setApplied(true)}>Simulate</button><button className="refresh-button" onClick={() => setApplied(false)}>Reset</button></div>
    {applied && valid && <div className="table-scroll"><table><caption>Hypothetical table · unofficial</caption><thead><tr><th>Pos</th><th>Club</th><th>Played</th><th>GD</th><th>Points</th></tr></thead><tbody>{projected.map((r,i) => <tr key={r.team.id}><td>{i+1}</td><th>{r.team.name}</th><td>{r.played}</td><td>{r.goals_for-r.goals_against}</td><td>{r.points}</td></tr>)}</tbody></table></div>}
  </section>;
}
