import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  History,
  RotateCcw,
} from 'lucide-react';
import { analysisService } from '../services/analysisService';
import { projectService } from '../services/projectService';
import { ApiError } from '../services/api';
import { formatDateTime } from '../utils/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';

const PAGE_LIMIT = 15;

export const AnalysisHistoryPage: React.FC = () => {
  const [projectId, setProjectId] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [page, setPage] = useState<number>(0);

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectService.listProjects(),
  });

  const historyQuery = useQuery({
    queryKey: [
      'analysis-runs',
      'history',
      { projectId, status, dateFrom, dateTo, page },
    ],
    queryFn: () =>
      analysisService.listAnalysisRuns({
        project_id: projectId !== 'all' ? Number(projectId) : undefined,
        status: status !== 'all' ? status : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: PAGE_LIMIT,
        offset: page * PAGE_LIMIT,
      }),
  });

  const projects = projectsQuery.data ?? [];
  const data = historyQuery.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_LIMIT));

  const hasActiveFilters =
    projectId !== 'all' || status !== 'all' || Boolean(dateFrom) || Boolean(dateTo);

  const handleResetFilters = () => {
    setProjectId('all');
    setStatus('all');
    setDateFrom('');
    setDateTo('');
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-lg font-bold text-app-text">
            Persisted Analysis Run History
          </h2>
          <p className="text-xs text-app-text-secondary">
            Audit historical regression impact analyses, status logs, and QA review outcomes.
          </p>
        </div>

        <Link to="/change-requests" className="btn-primary shrink-0 text-xs">
          Run New Analysis
        </Link>
      </div>

      {/* Filters */}
      <section className="surface-card p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label htmlFor="history-project" className="field-label">
              Project
            </label>
            <select
              id="history-project"
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                setPage(0);
              }}
              className="input-field"
            >
              <option value="all">All Projects</option>
              {projects.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="history-status" className="field-label">
              Analysis Status
            </label>
            <select
              id="history-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(0);
              }}
              className="input-field"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="running">Running</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div>
            <label htmlFor="history-date-from" className="field-label">
              From Date (UTC)
            </label>
            <input
              id="history-date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(0);
              }}
              className="input-field"
            />
          </div>

          <div>
            <label htmlFor="history-date-to" className="field-label">
              To Date (UTC)
            </label>
            <input
              id="history-date-to"
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(0);
              }}
              className="input-field"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              disabled={!hasActiveFilters}
              onClick={handleResetFilters}
              className="btn-secondary w-full"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Filters
            </button>
          </div>
        </div>
      </section>

      {historyQuery.isLoading && (
        <LoadingSkeleton rows={6} message="Loading analysis run history..." />
      )}

      {historyQuery.isError && (
        <ErrorState
          title="Could not load analysis history"
          message={
            historyQuery.error instanceof ApiError
              ? historyQuery.error.message
              : 'Failed to retrieve persisted analysis runs.'
          }
          onRetry={() => historyQuery.refetch()}
        />
      )}

      {!historyQuery.isLoading && !historyQuery.isError && items.length === 0 && (
        <EmptyState
          title="No Analysis Runs Found"
          description={
            hasActiveFilters
              ? 'No analysis runs match your selected filters. Try adjusting or resetting the filter criteria.'
              : 'No impact analyses have been executed yet. Trigger one from Change Requests.'
          }
          icon={<History className="h-6 w-6" />}
          action={
            hasActiveFilters ? (
              <button type="button" onClick={handleResetFilters} className="btn-secondary">
                Clear Filters
              </button>
            ) : (
              <Link to="/change-requests" className="btn-primary">
                Go to Change Requests
              </Link>
            )
          }
        />
      )}

      {!historyQuery.isLoading && !historyQuery.isError && items.length > 0 && (
        <section className="surface-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                <tr>
                  <th className="px-4 py-3">Run ID</th>
                  <th className="px-4 py-3">Change Request</th>
                  <th className="px-4 py-3">Project</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Recommendations</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Completed</th>
                  <th className="px-5 py-3 text-right">Results</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border">
                {items.map((run) => (
                  <tr key={run.id} className="hover:bg-app-muted/35">
                    <td className="px-4 py-3 font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                      <Link
                        to={`/impact-analysis?runId=${run.id}`}
                        className="hover:underline"
                      >
                        RUN-{run.id}
                      </Link>
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <p className="truncate font-semibold text-app-text">
                        {run.change_request_title ?? 'Deleted Change Request'}
                      </p>
                      {run.change_request_id && (
                        <span className="font-mono text-[11px] text-app-text-secondary">
                          CR-{run.change_request_id}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs font-medium text-app-text-secondary">
                      {run.project_name ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={run.status} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-app-text">
                      {run.total_recommendations}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-app-text-secondary">
                      {formatDateTime(run.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-app-text-secondary">
                      {formatDateTime(run.completed_at)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link
                        to={`/impact-analysis?runId=${run.id}`}
                        className="inline-flex items-center gap-1 rounded-md border border-app-border-strong bg-app-surface px-2.5 py-1 text-xs font-semibold text-app-text transition-colors hover:bg-app-muted"
                      >
                        View Results
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="flex flex-col gap-3 border-t border-app-border px-5 py-3.5 text-xs text-app-text-secondary sm:flex-row sm:items-center sm:justify-between">
            <span>
              Showing{' '}
              <strong className="font-mono text-app-text">
                {page * PAGE_LIMIT + 1}–{Math.min((page + 1) * PAGE_LIMIT, total)}
              </strong>{' '}
              of <strong className="font-mono text-app-text">{total}</strong> persisted run(s)
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="btn-secondary py-1 px-2.5 text-xs"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Previous
              </button>
              <span className="font-mono">
                Page {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="btn-secondary py-1 px-2.5 text-xs"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

