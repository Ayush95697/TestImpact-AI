import React from 'react';
import { AlertCircle, Inbox, RefreshCw } from 'lucide-react';

export const LoadingSkeleton: React.FC<{ rows?: number; message?: string }> = ({
  rows = 4,
  message = 'Loading records...',
}) => {
  return (
    <div className="surface-card p-6" role="status" aria-busy="true">
      <div className="mb-4 flex items-center gap-2.5 text-sm text-app-text-secondary">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-indigo-500" />
        <span>{message}</span>
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, idx) => (
          <div
            key={idx}
            className="h-9 w-full animate-pulse rounded-md bg-app-muted"
          />
        ))}
      </div>
    </div>
  );
};

export const EmptyState: React.FC<{
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}> = ({ title, description, action, icon }) => {
  return (
    <div className="surface-card flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-app-muted text-app-text-secondary">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <h3 className="text-base font-bold text-app-text">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm text-app-text-secondary">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
};

export const ErrorState: React.FC<{
  title?: string;
  message: string;
  onRetry?: () => void;
}> = ({ title = 'Unable to load data', message, onRetry }) => {
  return (
    <div
      className="surface-card border-red-200 p-6 dark:border-red-900/50"
      role="alert"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
          <div>
            <h3 className="text-sm font-bold text-app-text">{title}</h3>
            <p className="mt-1 text-sm text-app-text-secondary">{message}</p>
          </div>
        </div>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-secondary shrink-0">
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        )}
      </div>
    </div>
  );
};

