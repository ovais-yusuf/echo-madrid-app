import Link from "next/link";
import { legacySiteUrl } from "@/lib/api";
import { NavLinks } from "./nav-links";

export function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="Echo Madrid home">
          <img src="/logo.png" width="44" height="44" alt="" />
          <span>
            ECHO <strong>MADRID</strong>
            <small>THE GAME, IN FOCUS.</small>
          </span>
        </Link>
        <NavLinks askHref={`${legacySiteUrl()}/#question`} />
      </div>
    </header>
  );
}
