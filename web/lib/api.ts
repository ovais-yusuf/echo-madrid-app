import "server-only";

export type Standing = {
  position: number;
  team: {
    id: number;
    name: string;
    short_name: string | null;
    crest_url: string | null;
  };
  played: number;
  won: number;
  drawn: number;
  lost: number;
  points: number;
  goals_for: number;
  goals_against: number;
  is_real_madrid: boolean;
};

export type StandingsResponse = {
  competition: {
    id: number;
    name: string;
    code: string | null;
    type: string | null;
  } | null;
  season: {
    id: number;
    year_label: string;
    start_date: string;
    end_date: string;
  } | null;
  updated_at: string | null;
  standings: Standing[];
};

export function legacySiteUrl(): string {
  return (process.env.LEGACY_SITE_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

export async function getStandings(): Promise<StandingsResponse> {
  const base = (process.env.API_BASE_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  const response = await fetch(`${base}/standings`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Standings unavailable");
  return response.json();
}

export function formatUpdatedAt(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return (
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    }).format(date) + " UTC"
  );
}

export type MatchCard = {
  id: number;
  utc_date: string;
  status: string;
  home_team: Standing["team"];
  away_team: Standing["team"];
  home_score: number | null;
  away_score: number | null;
  matchday: number | null;
  competition: NonNullable<StandingsResponse["competition"]>;
  season: NonNullable<StandingsResponse["season"]>;
};

export type MatchesResponse = {
  team: Standing["team"] | null;
  matches: MatchCard[];
  competitions: NonNullable<StandingsResponse["competition"]>[];
  seasons: string[];
  selected_season: string | null;
  imported_at: string | null;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export async function getMatches(
  params: URLSearchParams,
): Promise<MatchesResponse> {
  const base = (process.env.API_BASE_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  const response = await fetch(`${base}/matches?${params}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Matches unavailable");
  return response.json();
}
