"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

export function RefreshButton({ label = "Refresh table" }: { label?: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      className="refresh-button"
      disabled={pending}
      aria-busy={pending}
      onClick={() => startTransition(() => router.refresh())}
    >
      <span
        className={pending ? "refresh-icon spinning" : "refresh-icon"}
        aria-hidden="true"
      >
        ↻
      </span>
      {pending ? "Refreshing…" : label}
    </button>
  );
}
