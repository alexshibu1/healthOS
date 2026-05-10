import { useCallback, useEffect, useState } from "react";
import snapshotData from "../data/snapshot.json";
import {
  isDashboardSnapshot,
  parseLoadedSnapshot,
} from "../data/loadSnapshot";
import { getApiBaseUrl } from "../lib/apiBase";
import type { SnapshotData } from "../types";

type AppMode = "loading" | "landing" | "dashboard";

export function useHealthBootstrap(): {
  mode: AppMode;
  snapshot: SnapshotData | null;
  refetch: () => Promise<void>;
} {
  const [mode, setMode] = useState<AppMode>("loading");
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);

  const refetch = useCallback(async () => {
    const bundled = parseLoadedSnapshot(snapshotData);
    if (!bundled) {
      setMode("landing");
      setSnapshot(null);
      return;
    }

    const api = getApiBaseUrl();

    try {
      const st = await fetch(`${api}/status`);
      if (st.ok) {
        const body = (await st.json()) as { has_data?: boolean };
        if (!body.has_data) {
          setMode("landing");
          setSnapshot(null);
          return;
        }
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
    void refetch();
  }, [refetch]);

  return { mode, snapshot, refetch };
}
