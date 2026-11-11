"use client";
import { useEffect, useTransition } from "react";
import { useRouter } from "next/navigation";
export function AutoRefresh() {
  const router = useRouter();
  const [pending, transition] = useTransition();
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible" && !pending) transition(() => router.refresh());
    }, 60_000);
    return () => clearInterval(timer);
  }, [router, pending]);
  return null;
}
