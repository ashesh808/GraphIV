"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { LibraryResult } from "@/lib/types";
import { Icon } from "./icon";

export function ConnectionNote({ status, message }: Pick<LibraryResult, "status" | "message">) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  if (status === "connected") return null;
  return (
    <div className={`connection-note ${status === "error" ? "connection-error" : ""}`} role="status">
      <span className="status-dot" aria-hidden="true" />
      <p><strong>{status === "example" ? "Example library" : "Research server unavailable"}</strong><span>{status === "example" ? "Sample reports to explore the workspace. Your live reports will appear when a server is connected." : message || "The library couldn’t be loaded. Please try again."}</span></p>
      <button className="text-button connection-retry" disabled={pending} onClick={() => startTransition(() => router.refresh())}>
        <Icon name="refresh" width="14" height="14" className={pending ? "spinning" : ""} />{pending ? "Checking…" : "Retry"}
      </button>
    </div>
  );
}
