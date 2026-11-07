import { useEffect, useState } from "react";
import { getForecast, getHardship, getTimeMachine } from "./api";
import type { ForecastResult, HardshipResult, TimeMachineRequest, TimeMachineResult } from "./types";

export type Loadable<T> = { data: T | null; loading: boolean; error: string | null };

const forecastCache = new Map<string, ForecastResult>();
const hardshipCache = new Map<string, HardshipResult>();

const OFFLINE_MSG = "The Heirloom backend is not reachable and there is no saved result for this view. Start it with: uvicorn backend.main:app --port 8000";

function useCached<T>(key: string, cache: Map<string, T>, load: () => Promise<T | null>): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>(() => ({ data: cache.get(key) ?? null, loading: !cache.has(key), error: null }));
  useEffect(() => {
    let live = true;
    const cached = cache.get(key);
    setState({ data: cached ?? null, loading: !cached, error: null });
    load()
      .then((r) => {
        if (!live) return;
        if (r) {
          cache.set(key, r);
          setState({ data: r, loading: false, error: null });
        } else setState({ data: cached ?? null, loading: false, error: cached ? null : OFFLINE_MSG });
      })
      .catch((e: Error) => live && setState({ data: cached ?? null, loading: false, error: e.message }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

export function useForecast(memberId: string) {
  return useCached(memberId, forecastCache, () => getForecast(memberId));
}

export function useHardship(memberId: string) {
  return useCached(memberId, hardshipCache, () => getHardship(memberId));
}

/** Forecasts for several members at once (Family page). */
export function useForecasts(ids: string[]) {
  const key = ids.join(",");
  const [data, setData] = useState<Record<string, ForecastResult | null>>({});
  useEffect(() => {
    let live = true;
    setData(Object.fromEntries(ids.map((id) => [id, forecastCache.get(id) ?? null])));
    ids.forEach((id) =>
      getForecast(id)
        .then((r) => {
          if (r) forecastCache.set(id, r);
          if (live) setData((d) => ({ ...d, [id]: r }));
        })
        .catch(() => live && setData((d) => ({ ...d, [id]: null }))),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return data;
}

/**
 * Time Machine: debounced while sliders move. Keeps showing the previous result until the new one
 * arrives (`updating`), and reports when a scenario has no live or saved result (`unavailable`).
 */
export function useTimeMachine(req: TimeMachineRequest) {
  const key = JSON.stringify(req);
  const [state, setState] = useState<{ data: TimeMachineResult | null; updating: boolean; unavailable: boolean; error: string | null }>({
    data: null,
    updating: true,
    unavailable: false,
    error: null,
  });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, updating: true }));
    const t = setTimeout(() => {
      getTimeMachine(req)
        .then((r) => {
          if (!live) return;
          if (r) setState({ data: r, updating: false, unavailable: false, error: null });
          else setState((s) => ({ ...s, updating: false, unavailable: true }));
        })
        .catch((e: Error) => live && setState((s) => ({ ...s, updating: false, error: e.message })));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
