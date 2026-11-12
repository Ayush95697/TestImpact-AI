import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
}

interface ToastContextValue {
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<ToastMessage, 'id'>) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setToasts((prev) => [...prev.slice(-3), { ...toast, id }]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
      }, 5000);
    },
    []
  );

  const success = useCallback(
    (title: string, description?: string) => addToast({ variant: 'success', title, description }),
    [addToast]
  );

  const error = useCallback(
    (title: string, description?: string) => addToast({ variant: 'error', title, description }),
    [addToast]
  );

  const warning = useCallback(
    (title: string, description?: string) => addToast({ variant: 'warning', title, description }),
    [addToast]
  );

  const info = useCallback(
    (title: string, description?: string) => addToast({ variant: 'info', title, description }),
    [addToast]
  );

  const stylesByVariant: Record<
    ToastVariant,
    { border: string; iconBg: string; icon: React.ReactNode }
  > = {
    success: {
      border: 'border-emerald-500/40 dark:border-emerald-500/30',
      iconBg: 'text-emerald-600 dark:text-emerald-400',
      icon: <CheckCircle2 className="h-5 w-5" />,
    },
    error: {
      border: 'border-red-500/40 dark:border-red-500/30',
      iconBg: 'text-red-600 dark:text-red-400',
      icon: <AlertCircle className="h-5 w-5" />,
    },
    warning: {
      border: 'border-amber-500/40 dark:border-amber-500/30',
      iconBg: 'text-amber-600 dark:text-amber-400',
      icon: <AlertTriangle className="h-5 w-5" />,
    },
    info: {
      border: 'border-indigo-500/40 dark:border-indigo-500/30',
      iconBg: 'text-indigo-600 dark:text-indigo-400',
      icon: <Info className="h-5 w-5" />,
    },
  };

  return (
    <ToastContext.Provider value={{ addToast, success, error, warning, info, dismissToast }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2 px-4 sm:px-0"
      >
        {toasts.map((toast) => {
          const style = stylesByVariant[toast.variant];
          return (
            <div
              key={toast.id}
              role="status"
              className={`pointer-events-auto flex items-start gap-3 rounded-lg border bg-app-surface p-3.5 shadow-lg ${style.border}`}
            >
              <span className={`mt-0.5 shrink-0 ${style.iconBg}`}>{style.icon}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-app-text">{toast.title}</p>
                {toast.description && (
                  <p className="mt-0.5 text-xs leading-relaxed text-app-text-secondary">
                    {toast.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss notification"
                className="rounded p-1 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

