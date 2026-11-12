import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Boxes,
  Bug,
  ClipboardCheck,
  FolderKanban,
  GitPullRequest,
  Plus,
} from 'lucide-react';
import { systemService } from '../services/systemService';
import { projectService } from '../services/projectService';
import { ApiError } from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { formatDateTime } from '../utils/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';
import { DashboardCharts } from '../components/dashboard/DashboardCharts';
import { ProjectFormModal } from '../components/projects/ProjectFormModal';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [createProjectOpen, setCreateProjectOpen] = useState(false);

  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => systemService.getDashboardSummary(),
  });

  const createProjectMutation = useMutation({
    mutationFn: (payload: { name: string; description: string | null }) =>
      projectService.createProject(payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setCreateProjectOpen(false);
      toast.success('Project created', `Project "${created.name}" is ready.`);
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to create project';
      toast.error('Could not create project', msg);
    },
  });

  const summary = summaryQuery.data;
  const latestRun = summary?.recent_analysis_runs?.[0];

  const handleViewImpactAnalysis = () => {
    const completedRun = summary?.recent_analysis_runs?.find((r) => r.status === 'completed');
    const target = completedRun ?? latestRun;
    if (target) {
      navigate(`/impact-analysis?runId=${target.id}`);
    } else {
      navigate('/impact-analysis');
    }
  };

  const kpiCards = summary
    ? [
        {
          label: 'Total Projects',
          value: summary.total_projects,
          icon: FolderKanban,
          accent: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50',
          to: '/projects',
        },
        {
          label: 'Total Modules',
          value: summary.total_modules,
          icon: Boxes,
          accent: 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/50',
          to: '/projects',
        },
        {
          label: 'Total Test Cases',
          value: summary.total_test_cases,
          icon: ClipboardCheck,
          accent: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50',
          to: '/projects',
        },
        {
          label: 'Total Defects',
          value: summary.total_defects,
          icon: Bug,
          accent: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50',
          to: '/projects',
        },
        {
          label: 'Change Requests',
          value: summary.total_change_requests,
          icon: GitPullRequest,
          accent: 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/50',
          to: '/change-requests',
        },
        {
          label: 'Analysis Runs',
          value: summary.total_analysis_runs,
          icon: Activity,
          accent: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50',
          to: '/analysis-history',
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Welcome Header & Quick Actions */}
      <section className="surface-card p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-heading text-xl font-bold text-app-text sm:text-2xl">
              Welcome to TestImpact AI
            </h2>
            <p className="mt-1 text-sm text-app-text-secondary">
              Understand change impact. Prioritize regression testing. Make QA decisions with evidence.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => setCreateProjectOpen(true)}
              className="btn-secondary"
            >
              <Plus className="h-4 w-4" />
              Create Project
            </button>
            <Link to="/change-requests?create=1" className="btn-secondary">
              <GitPullRequest className="h-4 w-4" />
              Create Change Request
            </Link>
            <button type="button" onClick={handleViewImpactAnalysis} className="btn-primary">
              <Activity className="h-4 w-4" />
              View Impact Analysis
            </button>
          </div>
        </div>
      </section>

      {summaryQuery.isLoading && (
        <LoadingSkeleton rows={5} message="Loading live metrics from FastAPI..." />
      )}

      {summaryQuery.isError && (
        <ErrorState
          title="Could not load dashboard metrics"
          message={
            summaryQuery.error instanceof ApiError
              ? summaryQuery.error.message
              : 'Unable to communicate with the backend API.'
          }
          onRetry={() => summaryQuery.refetch()}
        />
      )}

      {summary && (
        <>
          {/* 6 KPI Metric Cards */}
          <section aria-label="Environment metrics" className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            {kpiCards.map((card) => {
              const Icon = card.icon;
              return (
                <Link
                  key={card.label}
                  to={card.to}
                  className="surface-card group p-4 transition-colors hover:border-indigo-500/40"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-app-text-secondary">
                      {card.label}
                    </span>
                    <span className={`rounded-md p-1.5 ${card.accent}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                  </div>
                  <p className="mt-3 font-mono text-2xl font-semibold text-app-text tabular-nums">
                    {card.value}
                  </p>
                </Link>
              );
            })}
          </section>

          {summary.total_projects === 0 ? (
            <EmptyState
              title="No Projects Configured Yet"
              description="Get started by creating your first software project, adding modules and test cases, and submitting a change request for impact analysis."
              action={
                <button
                  type="button"
                  onClick={() => setCreateProjectOpen(true)}
                  className="btn-primary"
                >
                  <Plus className="h-4 w-4" />
                  Create First Project
                </button>
              }
            />
          ) : (
            <>
              {/* Visualizations */}
              <DashboardCharts
                impactDistribution={summary.impact_level_distribution}
                executionDistribution={summary.execution_status_distribution}
                projectsOverview={summary.projects_overview}
              />

              {/* Recent Analysis Activity & Project Overview */}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                {/* Recent Analysis Activity */}
                <section className="surface-card overflow-hidden xl:col-span-2">
                  <div className="flex items-center justify-between border-b border-app-border px-5 py-4">
                    <div>
                      <h3 className="text-sm font-bold text-app-text">
                        Recent Analysis Activity
                      </h3>
                      <p className="text-xs text-app-text-secondary">
                        Latest persisted regression impact runs across all projects
                      </p>
                    </div>
                    <Link
                      to="/analysis-history"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      View all
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>

                  {summary.recent_analysis_runs.length === 0 ? (
                    <div className="p-8 text-center">
                      <p className="text-sm font-medium text-app-text">
                        No impact analysis runs recorded yet
                      </p>
                      <p className="mt-1 text-xs text-app-text-secondary">
                        Open Change Requests and run Analyse Impact to generate ranked recommendations.
                      </p>
                      <Link to="/change-requests" className="btn-primary mt-4 inline-flex">
                        Go to Change Requests
                      </Link>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                          <tr>
                            <th className="px-5 py-3">Change Request</th>
                            <th className="px-4 py-3">Project</th>
                            <th className="px-4 py-3">Status</th>
                            <th className="px-4 py-3 text-right">Recommendations</th>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-5 py-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-app-border">
                          {summary.recent_analysis_runs.map((run) => (
                            <tr
                              key={run.id}
                              className="transition-colors hover:bg-app-muted/40"
                            >
                              <td className="px-5 py-3">
                                <div className="font-medium text-app-text">
                                  {run.change_request_title ?? 'Deleted Change Request'}
                                </div>
                                <div className="font-mono text-xs text-app-text-secondary">
                                  Run #{run.id}
                                  {run.change_request_id ? ` · CR #${run.change_request_id}` : ''}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-app-text-secondary">
                                {run.project_name ?? '—'}
                              </td>
                              <td className="px-4 py-3">
                                <StatusBadge value={run.status} />
                              </td>
                              <td className="px-4 py-3 text-right font-mono font-medium text-app-text">
                                {run.total_recommendations}
                              </td>
                              <td className="whitespace-nowrap px-4 py-3 text-xs text-app-text-secondary">
                                {formatDateTime(run.created_at)}
                              </td>
                              <td className="px-5 py-3 text-right">
                                <Link
                                  to={`/impact-analysis?runId=${run.id}`}
                                  className="inline-flex items-center gap-1 rounded-md border border-app-border-strong px-2.5 py-1 text-xs font-medium text-app-text hover:bg-app-muted"
                                >
                                  Inspect
                                  <ArrowRight className="h-3 w-3" />
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                {/* Project Overview */}
                <section className="surface-card overflow-hidden">
                  <div className="flex items-center justify-between border-b border-app-border px-5 py-4">
                    <div>
                      <h3 className="text-sm font-bold text-app-text">Project Overview</h3>
                      <p className="text-xs text-app-text-secondary">
                        Registered repositories & QA inventory
                      </p>
                    </div>
                    <Link
                      to="/projects"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      Manage
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                  <div className="divide-y divide-app-border">
                    {summary.projects_overview.map((proj) => (
                      <Link
                        key={proj.id}
                        to={`/projects?projectId=${proj.id}`}
                        className="flex items-center justify-between gap-3 px-5 py-3.5 transition-colors hover:bg-app-muted/40"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-app-text">
                            {proj.name}
                          </p>
                          <p className="truncate text-xs text-app-text-secondary">
                            {proj.description || `Project ID #${proj.id}`}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3 font-mono text-xs text-app-text-secondary">
                          <span title="Modules">{proj.module_count} mod</span>
                          <span className="text-app-border-strong">|</span>
                          <span className="font-semibold text-app-text" title="Test Cases">
                            {proj.test_case_count} TC
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                </section>
              </div>
            </>
          )}
        </>
      )}

      <ProjectFormModal
        isOpen={createProjectOpen}
        onClose={() => setCreateProjectOpen(false)}
        onSubmit={async (values) => {
          await createProjectMutation.mutateAsync(values);
        }}
        isSubmitting={createProjectMutation.isPending}
      />
    </div>
  );
};

