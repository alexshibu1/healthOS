import { useCallback, useEffect, useState } from "react";
import snapshotData from "../data/snapshot.json";
import {
  isDashboardSnapshot,
  parseLoadedSnapshot,
} from "../data/loadSnapshot";
import { getApiBaseUrl } from "../lib/apiBase";
import type { SnapshotData } from "../types";

type AppMode = "loading" | "landing" | "dashboard";

/**
 * One GET /snapshot replaces /status + /snapshot: same truth (dashboard vs not),
 * half the round trips. Bundled JSON is only used when the API is unreachable or
 * returns a non-404 error (aligned with previous /status-not-ok fallback).
 */
export function useHealthBootstrap(): {
  mode: AppMode;
  snapshot: SnapshotData | null;
} {
  const [mode, setMode] = useState<AppMode>("loading");
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);

  const bootstrap = useCallback(async () => {
    const bundled = parseLoadedSnapshot(snapshotData);
    if (!bundled) {
      setMode("landing");
      setSnapshot(null);
      return;
    }

    const api = getApiBaseUrl();

    try {
      const snapRes = await fetch(`${api}/snapshot`);
      if (snapRes.ok) {
        const json: unknown = await snapRes.json();
        const parsed = parseLoadedSnapshot(json);
        if (parsed && isDashboardSnapshot(parsed)) {
          setSnapshot(parsed);
          setMode("dashboard");
          return;
        }
        setMode("landing");
        setSnapshot(null);
        return;
      }
      if (snapRes.status === 404) {
        setMode("landing");
        setSnapshot(null);
        return;
      }
    } catch {
      /* fall through to bundled snapshot */
    }

    if (isDashboardSnapshot(bundled)) {
      setSnapshot(bundled);
      setMode("dashboard");
    } else {
      setMode("landing");
      setSnapshot(null);
    }
  }, []);

  useEffect(() => {
    // Schedule so the effect body does not invoke bootstrap synchronously (react-hooks/set-state-in-effect).
    const id = window.setTimeout(() => {
      void bootstrap();
    }, 0);
    return () => window.clearTimeout(id);
  }, [bootstrap]);

  return { mode, snapshot };
}
