import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Activity,
  Check,
  ChevronDown,
  ChevronRight,
  GitPullRequest,
  Layers,
  Loader2,
  X,
} from 'lucide-react';
import { analysisService } from '../services/analysisService';
import { changeRequestService } from '../services/changeRequestService';
import { projectService } from '../services/projectService';
import { moduleService } from '../services/moduleService';
import { llmService } from '../services/llmService';
import { ApiError } from '../services/api';
import { useSystemCapabilities } from '../hooks/useSystemStatus';
import { useToast } from '../contexts/ToastContext';
import { formatDateTime, formatScore } from '../utils/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';
import { AIExplanationPanel } from '../components/analysis/AIExplanationPanel';
import { RecommendationExpandedDetail } from '../components/analysis/RecommendationExpandedDetail';
import type { AnalysisRunDetail, Recommendation } from '../types/api';

export const ImpactAnalysisPage: React.FC = () => {
  const { runId: routeRunId } = useParams<{ runId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const capabilitiesQuery = useSystemCapabilities();
  const llmAvailable = Boolean(capabilitiesQuery.data?.llm_explanations_available);

  const [expandedRecId, setExpandedRecId] = useState<number | null>(null);
  const [impactFilter, setImpactFilter] = useState<string>('all');
  const [reviewFilter, setReviewFilter] = useState<string>('all');
  const [reviewingRecId, setReviewingRecId] = useState<number | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);

  // Recent runs list so /impact-analysis without an ID resolves cleanly and lets QA switch runs
  const recentRunsQuery = useQuery({
    queryKey: ['analysis-runs', 'switcher'],
    queryFn: () => analysisService.listAnalysisRuns({ limit: 25, offset: 0 }),
  });

  const explicitRunIdParam = routeRunId ?? searchParams.get('runId');
  const parsedExplicitRunId = explicitRunIdParam ? Number(explicitRunIdParam) : NaN;

  const activeRunId = useMemo(() => {
    if (Number.isFinite(parsedExplicitRunId) && parsedExplicitRunId > 0) {
      return parsedExplicitRunId;
    }
    const items = recentRunsQuery.data?.items ?? [];
    const latestCompleted = items.find((r) => r.status === 'completed');
    return (latestCompleted ?? items[0])?.id ?? null;
  }, [parsedExplicitRunId, recentRunsQuery.data?.items]);

  const runDetailQuery = useQuery({
    queryKey: ['analysis-runs', 'detail', activeRunId],
    queryFn: () => analysisService.getAnalysisRun(activeRunId!),
    enabled: activeRunId !== null,
  });

  const run = runDetailQuery.data;

  const crQuery = useQuery({
    queryKey: ['change-requests', 'detail', run?.change_request_id],
    queryFn: () => changeRequestService.getChangeRequest(run!.change_request_id!),
    enabled: Boolean(run?.change_request_id),
    staleTime: 60000,
  });

  const changeRequest = crQuery.data;

  const projectQuery = useQuery({
    queryKey: ['projects', 'detail', changeRequest?.project_id],
    queryFn: () => projectService.getProject(changeRequest!.project_id),
    enabled: Boolean(changeRequest?.project_id),
    staleTime: 60000,
  });

  const modulesQuery = useQuery({
    queryKey: ['projects', changeRequest?.project_id, 'modules'],
    queryFn: () => moduleService.listByProject(changeRequest!.project_id),
    enabled: Boolean(changeRequest?.project_id),
    staleTime: 60000,
  });

  const explanationQuery = useQuery({
    queryKey: ['analysis-runs', 'explanation', activeRunId],
    queryFn: () => llmService.getExplanation(activeRunId!),
    enabled: activeRunId !== null && run?.status === 'completed',
    retry: false,
  });

  const explainMutation = useMutation({
    mutationFn: (id: number) => llmService.generateExplanation(id),
    onMutate: () => {
      setExplainError(null);
    },
    onSuccess: (generated) => {
      queryClient.setQueryData(
        ['analysis-runs', 'explanation', generated.analysis_run_id],
        generated
      );
      toast.success(
        'AI explanation ready',
        `Generated advisory summary using ${generated.model_name}.`
      );
    },
    onError: (err) => {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Failed to generate AI explanation. Deterministic analysis remains intact.';
      setExplainError(msg);
      toast.error('AI explanation failed', msg);
    },
  });

  const handleReviewDecision = async (
    rec: Recommendation,
    decision: 'accepted' | 'rejected'
  ) => {
    if (reviewingRecId !== null || !activeRunId) return;
    setReviewingRecId(rec.id);
    try {
      const updated = await analysisService.reviewRecommendation(rec.id, decision);
      queryClient.setQueryData<AnalysisRunDetail>(
        ['analysis-runs', 'detail', activeRunId],
        (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            recommendations: prev.recommendations.map((item) =>
              item.id === updated.id
                ? { ...item, review_status: updated.review_status }
                : item
            ),
          };
        }
      );
      toast.success(
        `Recommendation #${rec.rank} ${decision}`,
        `Test case "${rec.test_case_title}" marked as ${decision}. Score (${formatScore(
          rec.score
        )}) and ranking preserved.`
      );
    } catch (err) {
      toast.error(
        'Could not update review decision',
        err instanceof ApiError ? err.message : 'Failed to submit review.'
      );
    } finally {
      setReviewingRecId(null);
    }
  };

  const affectedModules = useMemo(() => {
    if (!changeRequest || !modulesQuery.data) return [];
    const idSet = new Set(changeRequest.module_ids);
    return modulesQuery.data.filter((m) => idSet.has(m.id));
  }, [changeRequest, modulesQuery.data]);

  const recommendations = run?.recommendations ?? [];

  const summaryCounts = useMemo(() => {
    let high = 0;
    let medium = 0;
    let low = 0;
    for (const r of recommendations) {
      const lvl = r.impact_level.trim().toLowerCase();
      if (lvl === 'high') high += 1;
      else if (lvl === 'medium') medium += 1;
      else if (lvl === 'low') low += 1;
    }
    return {
      high,
      medium,
      low,
      total: run?.total_recommendations ?? recommendations.length,
    };
  }, [recommendations, run?.total_recommendations]);

  const filteredRecommendations = useMemo(() => {
    return recommendations.filter((r) => {
      if (impactFilter !== 'all' && r.impact_level.toLowerCase() !== impactFilter) {
        return false;
      }
      if (reviewFilter !== 'all' && r.review_status.toLowerCase() !== reviewFilter) {
        return false;
      }
      return true;
    });
  }, [recommendations, impactFilter, reviewFilter]);

  const handleSelectRun = (nextId: number) => {
    setExpandedRecId(null);
    setExplainError(null);
    if (routeRunId) {
      navigate(`/impact-analysis?runId=${nextId}`);
    } else {
      setSearchParams({ runId: String(nextId) });
    }
  };

  const runsList = recentRunsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Top Workspace Control Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-lg font-bold text-app-text">
            Regression Impact Analysis Workspace
          </h2>
          <p className="text-xs text-app-text-secondary">
            Deterministic candidate scoring, supporting evidence trace, and QA review decisions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {runsList.length > 0 && (
            <select
              aria-label="Select analysis run"
              value={activeRunId ?? ''}
              onChange={(e) => {
                const id = Number(e.target.value);
                if (id > 0) handleSelectRun(id);
              }}
              className="input-field w-full sm:w-auto sm:min-w-[260px] text-xs font-medium"
            >
              {runsList.map((item) => (
                <option key={item.id} value={item.id}>
                  Run #{item.id} — {item.change_request_title ?? 'Deleted CR'} ({item.status})
                </option>
              ))}
            </select>
          )}
          <Link to="/change-requests" className="btn-secondary shrink-0 text-xs">
            <GitPullRequest className="h-3.5 w-3.5" />
            New Analysis
          </Link>
        </div>
      </div>

      {recentRunsQuery.isLoading && !activeRunId && (
        <LoadingSkeleton rows={4} message="Checking analysis runs..." />
      )}

      {!recentRunsQuery.isLoading && activeRunId === null && (
        <EmptyState
          title="No Impact Analysis Runs Yet"
          description="Select or create a Change Request and click Analyse Impact to evaluate affected regression test cases."
          icon={<Activity className="h-6 w-6" />}
          action={
            <Link to="/change-requests" className="btn-primary">
              Go to Change Requests
            </Link>
          }
        />
      )}

      {activeRunId !== null && runDetailQuery.isLoading && (
        <LoadingSkeleton rows={6} message={`Loading Analysis Run #${activeRunId}...`} />
      )}

      {activeRunId !== null && runDetailQuery.isError && (
        <ErrorState
          title={`Could not load Analysis Run #${activeRunId}`}
          message={
            runDetailQuery.error instanceof ApiError
              ? runDetailQuery.error.message
              : 'Failed to retrieve analysis run details.'
          }
          onRetry={() => runDetailQuery.refetch()}
        />
      )}

      {run && (
        <>
          {/* Analysis Result Header */}
          <section className="surface-card p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-2.5 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-indigo-50 px-2 py-0.5 font-mono text-xs font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                    RUN-{run.id}
                  </span>
                  <StatusBadge value={run.status} />
                  {projectQuery.data && (
                    <span className="rounded bg-app-muted px-2.5 py-0.5 text-xs font-semibold text-app-text">
                      {projectQuery.data.name}
                    </span>
                  )}
                  {run.change_request_id && (
                    <span className="font-mono text-xs text-app-text-secondary">
                      CR #{run.change_request_id}
                    </span>
                  )}
                </div>

                <h3 className="font-heading text-xl font-bold text-app-text">
                  {changeRequest?.title ??
                    (run.change_request_id
                      ? `Change Request #${run.change_request_id}`
                      : 'Deleted Change Request')}
                </h3>

                {changeRequest?.description && (
                  <p className="max-w-4xl text-sm leading-relaxed text-app-text-secondary">
                    {changeRequest.description}
                  </p>
                )}

                {affectedModules.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-xs font-semibold text-app-text-secondary mr-1">
                      Affected Modules:
                    </span>
                    {affectedModules.map((mod) => (
                      <span
                        key={mod.id}
                        className="inline-flex items-center gap-1 rounded border border-app-border bg-app-muted/70 px-2 py-0.5 text-xs font-medium text-app-text"
                      >
                        <Layers className="h-3 w-3 text-teal-600 dark:text-teal-400" />
                        {mod.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="shrink-0 space-y-1.5 rounded-md border border-app-border bg-app-muted/40 px-4 py-3 text-xs lg:min-w-[230px]">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-app-text-secondary">Total Recommendations</span>
                  <span className="font-mono font-bold text-app-text">
                    {run.total_recommendations}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-app-text-secondary">Created</span>
                  <span className="font-medium text-app-text">
                    {formatDateTime(run.created_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-app-text-secondary">Completed</span>
                  <span className="font-medium text-app-text">
                    {formatDateTime(run.completed_at)}
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* 4 Summary Metric Cards */}
          <section
            aria-label="Impact level summary metrics"
            className="grid grid-cols-2 gap-4 lg:grid-cols-4"
          >
            <div className="surface-card border-l-4 border-l-red-600 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                High Impact
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-red-600 dark:text-red-400">
                {summaryCounts.high}
              </p>
              <p className="mt-1 text-[11px] text-app-text-secondary">
                Heuristic score &ge; 70 pts
              </p>
            </div>

            <div className="surface-card border-l-4 border-l-amber-600 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                Medium Impact
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-amber-600 dark:text-amber-400">
                {summaryCounts.medium}
              </p>
              <p className="mt-1 text-[11px] text-app-text-secondary">
                Heuristic score 40 – 69.9 pts
              </p>
            </div>

            <div className="surface-card border-l-4 border-l-teal-600 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                Low Impact
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-teal-600 dark:text-teal-400">
                {summaryCounts.low}
              </p>
              <p className="mt-1 text-[11px] text-app-text-secondary">
                Heuristic score &lt; 40 pts
              </p>
            </div>

            <div className="surface-card border-l-4 border-l-indigo-600 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                Total Recommended
              </p>
              <p className="mt-2 font-mono text-2xl font-bold text-app-text">
                {summaryCounts.total}
              </p>
              <p className="mt-1 text-[11px] text-app-text-secondary">
                Additive multi-signal scoring (0–100)
              </p>
            </div>
          </section>

          {/* Conditional LLM Advisory Explanation Panel */}
          <AIExplanationPanel
            explanation={explanationQuery.data ?? null}
            recommendations={recommendations}
            isLoadingInitial={explanationQuery.isLoading}
            isGenerating={explainMutation.isPending}
            generationError={explainError}
            llmAvailable={llmAvailable}
            canGenerate={run.status === 'completed' && recommendations.length > 0}
            onGenerate={() => {
              if (!explainMutation.isPending) {
                explainMutation.mutate(run.id);
              }
            }}
          />

          {/* Ranked Recommendations Table */}
          <section className="surface-card overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-app-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-bold text-app-text">
                  Ranked Regression Test Recommendations
                </h3>
                <p className="text-xs text-app-text-secondary">
                  Click any row to inspect test steps, heuristic score breakdown, supporting evidence, defects, and execution logs.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  aria-label="Filter recommendations by impact level"
                  value={impactFilter}
                  onChange={(e) => setImpactFilter(e.target.value)}
                  className="input-field w-auto py-1.5 text-xs"
                >
                  <option value="all">All Impact Levels</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select
                  aria-label="Filter recommendations by QA review status"
                  value={reviewFilter}
                  onChange={(e) => setReviewFilter(e.target.value)}
                  className="input-field w-auto py-1.5 text-xs"
                >
                  <option value="all">All Review Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="accepted">Accepted</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>

            {recommendations.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-sm font-semibold text-app-text">
                  {run.status === 'failed'
                    ? 'Analysis run did not complete'
                    : 'No candidate test cases met impact thresholds'}
                </p>
                <p className="mt-1 text-xs text-app-text-secondary">
                  {run.status === 'failed'
                    ? 'Verify vector embeddings configuration and re-run impact analysis from Change Requests.'
                    : 'Ensure test cases are mapped to affected modules or indexed into the project vector store.'}
                </p>
              </div>
            ) : filteredRecommendations.length === 0 ? (
              <div className="p-8 text-center text-xs text-app-text-secondary">
                No recommendations match your active filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                    <tr>
                      <th className="w-8 px-3 py-3"></th>
                      <th className="px-3 py-3">Rank</th>
                      <th className="px-3 py-3">Test Case</th>
                      <th className="px-3 py-3">Impact Level</th>
                      <th className="px-3 py-3">Heuristic Score</th>
                      <th className="px-3 py-3">Primary Reason</th>
                      <th className="px-3 py-3">Review Status</th>
                      <th className="px-5 py-3 text-right">QA Review</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-app-border">
                    {filteredRecommendations.map((rec) => {
                      const isExpanded = expandedRecId === rec.id;
                      const isReviewing = reviewingRecId === rec.id;
                      const isAccepted = rec.review_status.toLowerCase() === 'accepted';
                      const isRejected = rec.review_status.toLowerCase() === 'rejected';

                      return (
                        <React.Fragment key={rec.id}>
                          <tr
                            className={`cursor-pointer transition-colors ${
                              isExpanded ? 'bg-app-muted/50' : 'hover:bg-app-muted/30'
                            }`}
                            onClick={() =>
                              setExpandedRecId(isExpanded ? null : rec.id)
                            }
                          >
                            <td className="px-3 py-3.5 align-top text-app-text-secondary">
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </td>
                            <td className="px-3 py-3.5 align-top font-mono text-xs font-bold text-app-text">
                              #{rec.rank}
                            </td>
                            <td className="px-3 py-3.5 align-top">
                              <span className="block font-mono text-xs text-app-text-secondary">
                                TC-{rec.test_case_id}
                              </span>
                              <span className="font-semibold text-app-text">
                                {rec.test_case_title}
                              </span>
                            </td>
                            <td className="px-3 py-3.5 align-top">
                              <StatusBadge value={rec.impact_level} />
                            </td>
                            <td className="px-3 py-3.5 align-top">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-app-text tabular-nums">
                                  {formatScore(rec.score)}
                                </span>
                                <span className="font-mono text-[10px] text-app-text-secondary">
                                  / 100
                                </span>
                              </div>
                            </td>
                            <td className="max-w-sm px-3 py-3.5 align-top text-xs leading-relaxed text-app-text-secondary">
                              <p className="line-clamp-2">{rec.reason}</p>
                            </td>
                            <td className="px-3 py-3.5 align-top">
                              <StatusBadge value={rec.review_status} />
                            </td>
                            <td
                              className="px-5 py-3.5 align-top text-right"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <div className="inline-flex items-center gap-1.5">
                                <button
                                  type="button"
                                  disabled={isReviewing || isAccepted}
                                  onClick={() => handleReviewDecision(rec, 'accepted')}
                                  className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed ${
                                    isAccepted
                                      ? 'border-emerald-300 bg-emerald-50 text-emerald-700 opacity-75 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300'
                                      : 'border-emerald-600/30 bg-app-surface text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/40'
                                  }`}
                                >
                                  {isReviewing ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <Check className="h-3 w-3" />
                                  )}
                                  Accept
                                </button>
                                <button
                                  type="button"
                                  disabled={isReviewing || isRejected}
                                  onClick={() => handleReviewDecision(rec, 'rejected')}
                                  className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed ${
                                    isRejected
                                      ? 'border-red-300 bg-red-50 text-red-700 opacity-75 dark:border-red-800 dark:bg-red-950/50 dark:text-red-300'
                                      : 'border-red-600/30 bg-app-surface text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40'
                                  }`}
                                >
                                  {isReviewing ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <X className="h-3 w-3" />
                                  )}
                                  Reject
                                </button>
                              </div>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan={8} className="p-0">
                                <RecommendationExpandedDetail
                                  recommendation={rec}
                                  projectId={changeRequest?.project_id ?? null}
                                />
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

