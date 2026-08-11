import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";

type AppDataContextType = {
  stats: any;
  cameras: any[];
  zones: any[];
  violations: any[];
  workers: any[];
  reports: any;
  loading: boolean;
  refetchAll: () => Promise<void>;
  refetchViolations: () => Promise<void>;
  refetchCameras: () => Promise<void>;
};

const AppDataContext = createContext<AppDataContextType>({
  stats: null,
  cameras: [],
  zones: [],
  violations: [],
  workers: [],
  reports: null,
  loading: true,
  refetchAll: async () => {},
  refetchViolations: async () => {},
  refetchCameras: async () => {},
});

const isBrowser = typeof window !== "undefined";

function safeGetItem<T>(key: string, defaultValue: T): T {
  if (!isBrowser) return defaultValue;
  try {
    const item = sessionStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function safeSetItem(key: string, value: any): void {
  if (!isBrowser) return;
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

export const DataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [stats, setStats] = useState<any>(() => safeGetItem("ev_stats", null));
  const [cameras, setCameras] = useState<any[]>(() => safeGetItem("ev_cameras", []));
  const [zones, setZones] = useState<any[]>(() => safeGetItem("ev_zones", []));
  const [violations, setViolations] = useState<any[]>(() => safeGetItem("ev_violations", []));
  const [workers, setWorkers] = useState<any[]>(() => safeGetItem("ev_workers", []));
  const [reports, setReports] = useState<any>(() => safeGetItem("ev_reports", null));
  const [loading, setLoading] = useState<boolean>(() => !safeGetItem("ev_stats", null));

  const initializedRef = useRef(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
        safeSetItem("ev_stats", data);
      }
    } catch (e) {}
  }, []);

  const fetchCameras = useCallback(async () => {
    try {
      const res = await fetch("/api/cameras");
      if (res.ok) {
        const data = await res.json();
        setCameras(data);
        safeSetItem("ev_cameras", data);
      }
    } catch (e) {}
  }, []);

  const fetchZones = useCallback(async () => {
    try {
      const res = await fetch("/api/zones");
      if (res.ok) {
        const data = await res.json();
        const list = data?.db_zones || [];
        setZones(list);
        safeSetItem("ev_zones", list);
      }
    } catch (e) {}
  }, []);

  const fetchViolations = useCallback(async () => {
    try {
      const res = await fetch("/api/violations");
      if (res.ok) {
        const data = await res.json();
        setViolations(data);
        safeSetItem("ev_violations", data);
      }
    } catch (e) {}
  }, []);

  const fetchWorkers = useCallback(async () => {
    try {
      const res = await fetch("/api/workers");
      if (res.ok) {
        const data = await res.json();
        setWorkers(data);
        safeSetItem("ev_workers", data);
      }
    } catch (e) {}
  }, []);

  const fetchReports = useCallback(async () => {
    try {
      const res = await fetch("/api/reports");
      if (res.ok) {
        const data = await res.json();
        setReports(data);
        safeSetItem("ev_reports", data);
      }
    } catch (e) {}
  }, []);

  const refetchAll = useCallback(async () => {
    await Promise.all([
      fetchStats(),
      fetchCameras(),
      fetchZones(),
      fetchViolations(),
      fetchWorkers(),
      fetchReports(),
    ]);
    setLoading(false);
  }, [fetchStats, fetchCameras, fetchZones, fetchViolations, fetchWorkers, fetchReports]);

  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      refetchAll();
    }

    // Background periodic sync every 10s without setting loading spinner
    const timer = setInterval(() => {
      fetchStats();
      fetchViolations();
    }, 10000);

    return () => clearInterval(timer);
  }, [refetchAll, fetchStats, fetchViolations]);

  return (
    <AppDataContext.Provider
      value={{
        stats,
        cameras,
        zones,
        violations,
        workers,
        reports,
        loading,
        refetchAll,
        refetchViolations: fetchViolations,
        refetchCameras: fetchCameras,
      }}
    >
      {children}
    </AppDataContext.Provider>
  );
};

export const useAppData = () => useContext(AppDataContext);
