import { useState, useEffect, useCallback, useRef } from 'react';

const isBrowser = typeof window !== 'undefined';

function safeGetItem(key: string): string | null {
  if (!isBrowser) return null;
  try { return sessionStorage.getItem(key); } catch { return null; }
}

function safeSetItem(key: string, value: string): void {
  if (!isBrowser) return;
  try { sessionStorage.setItem(key, value); } catch {}
}

function safeRemoveItem(key: string): void {
  if (!isBrowser) return;
  try { sessionStorage.removeItem(key); } catch {}
}

export function useSessionFetch<T>(url: string, defaultValue: T) {
  const [data, setData] = useState<T>(() => {
    const cached = safeGetItem(url);
    if (cached) {
      try { return JSON.parse(cached); } catch {}
    }
    return defaultValue;
  });
  
  const [loading, setLoading] = useState<boolean>(!safeGetItem(url));
  const [error, setError] = useState<Error | null>(null);
  const fetchedRef = useRef(false);

  const fetchData = useCallback(async (force = false) => {
    if (force) setLoading(true);
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error('Network response was not ok');
      const json = await res.json();
      
      safeSetItem(url, JSON.stringify(json));
      
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    if (!fetchedRef.current) {
      fetchedRef.current = true;
      fetchData();
    }
  }, [fetchData]);

  const mutate = useCallback((newData?: T) => {
    if (newData) {
      safeSetItem(url, JSON.stringify(newData));
      setData(newData);
    } else {
      fetchData(true);
    }
  }, [fetchData, url]);

  const clearCache = useCallback(() => {
    safeRemoveItem(url);
  }, [url]);

  return { data, loading, error, refetch: fetchData, mutate, clearCache };
}

// Global utility for invalidating session cache across the app
export const invalidateSessionCache = (url: string) => {
  safeRemoveItem(url);
};
