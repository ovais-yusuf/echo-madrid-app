"use client";

import { useState } from "react";

type Club = {
  name: string;
  short_name: string | null;
  crest_url: string | null;
};
export function ClubCrest({ team, size = 28 }: { team: Club; size?: number }) {
  const [failed, setFailed] = useState(false);
  const url = team.crest_url;
  if (!url || failed || !/^https?:\/\//i.test(url))
    return (
      <span
        className="crest-fallback"
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        {(team.short_name || team.name).slice(0, 2).toUpperCase()}
      </span>
    );
  return (
    <img
      className="club-crest"
      src={url}
      width={size}
      height={size}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
