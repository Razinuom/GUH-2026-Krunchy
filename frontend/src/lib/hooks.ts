import { useEffect, useState } from "react";
import { getForecast, getTimeMachine, type TimeMachineRequest } from "./api";
import { simulateForecast, simulateTimeMachine, type ForecastResult, type TimeMachineResult } from "./simulate";

const forecastCache = new Map<string, ForecastResult>();

/** Shows the local simulation straight away, then swaps in the backend result if it arrives. */
export function useForecast(memberId: string) {
  const [data, setData] = useState<ForecastResult>(() => forecastCache.get(memberId) ?? simulateForecast(memberId));
  useEffect(() => {
    let live = true;
    const cached = forecastCache.get(memberId) ?? simulateForecast(memberId);
    setData(cached);
    getForecast(memberId).then((r) => {
      forecastCache.set(memberId, r);
      if (live) setData(r);
    });
    return () => {
      live = false;
    };
  }, [memberId]);
  return data;
}

export function useForecasts(ids: string[]) {
  const key = ids.join(",");
  const [data, setData] = useState<Record<string, ForecastResult>>({});
  useEffect(() => {
    let live = true;
    const local = Object.fromEntries(ids.map((id) => [id, forecastCache.get(id) ?? simulateForecast(id)]));
    setData(local);
    Promise.all(ids.map((id) => getForecast(id))).then((rs) => {
      rs.forEach((r) => forecastCache.set(r.member_id, r));
      if (live) setData(Object.fromEntries(rs.map((r) => [r.member_id, r])));
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return data;
}

export function useTimeMachine(req: TimeMachineRequest) {
  const [data, setData] = useState<TimeMachineResult>(() => simulateTimeMachine(req));
  const key = JSON.stringify(req);
  useEffect(() => {
    let live = true;
    setData(simulateTimeMachine(req));
    // debounce backend calls while a slider is dragged
    const t = setTimeout(() => {
      getTimeMachine(req).then((r) => live && setData(r));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return data;
}
