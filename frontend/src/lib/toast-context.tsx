import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2 } from "lucide-react";

type ToastMessage = {
  id: string;
  message: string;
};

type ToastContextType = {
  showToast: (message: string, durationMs?: number) => void;
};

const ToastContext = createContext<ToastContextType>({
  showToast: () => {},
});

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const showToast = useCallback((message: string, durationMs: number = 2000) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToast({ id, message });

    setTimeout(() => {
      setToast((current) => (current?.id === id ? null : current));
    }, durationMs);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none transition-all duration-200 animate-in fade-in slide-in-from-top-4">
          <div className="flex items-center gap-2 rounded-full border border-success/50 bg-zinc-900/95 px-4 py-2 shadow-2xl backdrop-blur text-xs font-semibold text-foreground">
            <CheckCircle2 className="size-4 text-success shrink-0" />
            <span className="telemetry tracking-wide text-success">{toast.message}</span>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);
