import type { Standing } from "./api";

/** One imaginary additional game; never an official tie-break calculation. */
export function simulateTable(rows: Standing[], home: number, away: number, homeGoals: number, awayGoals: number): Standing[] {
  if (home === away || ![home, away].every(id => rows.some(row => row.team.id === id))) {
    throw new Error("Choose two different clubs from this table.");
  }
  if (![homeGoals, awayGoals].every(score => Number.isInteger(score) && score >= 0 && score <= 30)) {
    throw new Error("Scores must be whole numbers from 0 to 30.");
  }
  return rows.map(row => {
    if (![home, away].includes(row.team.id)) return {...row};
    const gf = row.team.id === home ? homeGoals : awayGoals;
    const ga = row.team.id === home ? awayGoals : homeGoals;
    return {...row, points: row.points + (gf > ga ? 3 : gf === ga ? 1 : 0),
      played: row.played + 1, won: row.won + Number(gf > ga),
      drawn: row.drawn + Number(gf === ga), lost: row.lost + Number(gf < ga),
      goals_for: row.goals_for + gf, goals_against: row.goals_against + ga};
  }).sort((a,b) => b.points - a.points || (b.goals_for - b.goals_against) - (a.goals_for - a.goals_against) || b.goals_for - a.goals_for || a.position - b.position);
}
