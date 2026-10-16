"use client";

import { useState } from "react";
import type { Standing } from "@/lib/api";
import { RefreshButton } from "./refresh-button";
import { ClubCrest } from "./club-crest";

export function StandingsTable({
  rows,
  season,
}: {
  rows: Standing[];
  season: string;
}) {
  const [search, setSearch] = useState("");
  const [madridOnly, setMadridOnly] = useState(false);
  const visible = rows.filter(
    (row) =>
      (!madridOnly || row.is_real_madrid) &&
      `${row.team.name} ${row.team.short_name || ""}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  return (
    <section className="table-card" aria-labelledby="table-title">
      <div className="table-heading">
        <div>
          <span className="eyebrow">THE FULL PICTURE</span>
          <h2 id="table-title">
            League table <span>{season}</span>
          </h2>
        </div>
        <RefreshButton />
      </div>
      <div className="table-controls">
        <label className="search-box">
          <span aria-hidden="true">⌕</span>
          <span className="sr-only">Search clubs</span>
          <input
            type="search"
            placeholder="Find a club…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <button
          className={`madrid-toggle ${madridOnly ? "selected" : ""}`}
          aria-pressed={madridOnly}
          onClick={() => setMadridOnly(!madridOnly)}
        >
          <span className="toggle-dot" aria-hidden="true" />
          Madrid only
        </button>
      </div>
      <div
        className="table-scroll"
        role="region"
        aria-label="Scrollable La Liga standings"
        tabIndex={0}
      >
        <table>
          <caption className="sr-only">
            La Liga standings for {season}, sorted by stored league position.
            All values come from the database.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="position">
                Pos
              </th>
              <th scope="col" className="club">
                Club
              </th>
              <th scope="col">
                <abbr title="Played">P</abbr>
              </th>
              <th scope="col">
                <abbr title="Won">W</abbr>
              </th>
              <th scope="col">
                <abbr title="Drawn">D</abbr>
              </th>
              <th scope="col">
                <abbr title="Lost">L</abbr>
              </th>
              <th scope="col">
                <abbr title="Goals for">GF</abbr>
              </th>
              <th scope="col">
                <abbr title="Goals against">GA</abbr>
              </th>
              <th scope="col">
                <abbr title="Goal difference">GD</abbr>
              </th>
              <th scope="col" className="points">
                Pts
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const gd = row.goals_for - row.goals_against;
              return (
                <tr
                  key={row.team.id}
                  className={row.is_real_madrid ? "madrid-row" : ""}
                >
                  <td className="position">
                    {String(row.position).padStart(2, "0")}
                  </td>
                  <th scope="row" className="club">
                    <span className="club-cell">
                      <ClubCrest team={row.team} />
                      <span>{row.team.short_name || row.team.name}</span>
                      {row.is_real_madrid && (
                        <span className="our-club">MADRID</span>
                      )}
                    </span>
                  </th>
                  <td>{row.played}</td>
                  <td>{row.won}</td>
                  <td>{row.drawn}</td>
                  <td>{row.lost}</td>
                  <td>{row.goals_for}</td>
                  <td>{row.goals_against}</td>
                  <td className={gd > 0 ? "positive" : ""}>
                    {gd > 0 ? "+" : ""}
                    {gd}
                  </td>
                  <td className="points">{row.points}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {visible.length === 0 && (
        <div className="no-results" role="status">
          No clubs match your filters.{" "}
          <button
            onClick={() => {
              setSearch("");
              setMadridOnly(false);
            }}
          >
            Clear filters
          </button>
        </div>
      )}
      <div className="table-bottom">
        <span>
          <i className="gold-dot" />
          Real Madrid highlighted
        </span>
        <span aria-live="polite">
          {visible.length} of {rows.length} clubs
        </span>
      </div>
    </section>
  );
}
