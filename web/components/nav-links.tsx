"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLinks({ askHref }: { askHref: string }) {
  const pathname = usePathname();
  return (
    <nav className="primary-nav" aria-label="Main navigation">
      {[
        { href: "/", label: "Home" },
        { href: "/standings", label: "Standings" },
        { href: "/matches", label: "Matches" },
        { href: "/team", label: "Team" },
      ].map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className={pathname === href ? "nav-active" : undefined}
          aria-current={pathname === href ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
      <a href={askHref} className="ask-nav">
        Ask Echo <span aria-hidden="true">↗</span>
      </a>
    </nav>
  );
}
