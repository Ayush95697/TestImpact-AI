import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  Edit3,
  GitPullRequest,
  Loader2,
  Play,
  Plus,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { changeRequestService } from '../services/changeRequestService';
import { projectService } from '../services/projectService';
import { moduleService } from '../services/moduleService';
import { analysisService } from '../services/analysisService';
import { ApiError } from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { formatDateTime } from '../utils/formatters';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';
import { ChangeRequestFormModal } from '../components/change-requests/ChangeRequestFormModal';
import type { ChangeRequest } from '../types/api';

export const ChangeRequestsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const initialProjectParam = searchParams.get('projectId') ?? 'all';
  const [projectFilter, setProjectFilter] = useState<string>(initialProjectParam);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingCr, setEditingCr] = useState<ChangeRequest | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ChangeRequest | null>(null);
  const [newlyCreatedCr, setNewlyCreatedCr] = useState<ChangeRequest | null>(null);
  const [analyzingCrId, setAnalyzingCrId] = useState<number | null>(null);
  const [analysisErrorBanner, setAnalysisErrorBanner] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('create') === '1') {
      setEditingCr(null);
      setFormModalOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete('create');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectService.listProjects(),
  });

  const changeRequestsQuery = useQuery({
    queryKey: ['change-requests'],
    queryFn: () => changeRequestService.listChangeRequests(),
  });

  const projects = projectsQuery.data ?? [];
  const changeRequests = changeRequestsQuery.data ?? [];

  const uniqueProjectIds = useMemo(
    () => Array.from(new Set(changeRequests.map((cr) => cr.project_id))),
    [changeRequests]
  );

  const moduleQueries = useQueries({
    queries: uniqueProjectIds.map((pid) => ({
      queryKey: ['projects', pid, 'modules'],
      queryFn: () => moduleService.listByProject(pid),
      staleTime: 60000,
    })),
  });

  const projectNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const p of projects) map.set(p.id, p.name);
    return map;
  }, [projects]);

  const moduleNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const q of moduleQueries) {
      for (const m of q.data ?? []) {
        map.set(m.id, m.name);
      }
    }
    return map;
  }, [moduleQueries]);

  const filteredRequests = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return changeRequests.filter((cr) => {
      if (projectFilter !== 'all' && cr.project_id !== Number(projectFilter)) {
        return false;
      }
      if (statusFilter !== 'all' && cr.status.toLowerCase() !== statusFilter.toLowerCase()) {
        return false;
      }
      if (q) {
        const matchesText =
          cr.title.toLowerCase().includes(q) ||
          cr.description.toLowerCase().includes(q) ||
          `cr-${cr.id}`.includes(q) ||
          String(cr.id) === q;
        if (!matchesText) return false;
      }
      return true;
    });
  }, [changeRequests, projectFilter, statusFilter, searchQuery]);

  const saveMutation = useMutation({
    mutationFn: async (values: {
      project_id: number;
      title: string;
      description: string;
      status: string;
      module_ids: number[];
    }) => {
      if (editingCr) {
        return changeRequestService.updateChangeRequest(editingCr.id, {
          title: values.title,
          description: values.description,
          status: values.status,
          module_ids: values.module_ids,
        });
      }
      return changeRequestService.createChangeRequest(values);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['change-requests'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
      setFormModalOpen(false);
      if (!editingCr) {
        setNewlyCreatedCr(saved);
        toast.success(
          'Change Request created',
          `CR #${saved.id} ("${saved.title}") is ready for impact analysis.`
        );
      } else {
        setEditingCr(null);
        toast.success('Change Request updated', `CR #${saved.id} saved.`);
      }
    },
    onError: (err) => {
      toast.error(
        'Could not save Change Request',
        err instanceof ApiError ? err.message : 'Validation or server error occurred.'
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (cr: ChangeRequest) => changeRequestService.deleteChangeRequest(cr.id),
    onSuccess: (_, cr) => {
      queryClient.invalidateQueries({ queryKey: ['change-requests'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
      if (newlyCreatedCr?.id === cr.id) setNewlyCreatedCr(null);
      setDeleteTarget(null);
      toast.success('Change Request deleted', `CR #${cr.id} was removed.`);
    },
    onError: (err) => {
      setDeleteTarget(null);
      toast.error(
        'Deletion failed',
        err instanceof ApiError ? err.message : 'Unable to delete change request.'
      );
    },
  });

  const handleAnalyzeImpact = async (cr: ChangeRequest) => {
    if (analyzingCrId !== null) return;
    setAnalyzingCrId(cr.id);
    setAnalysisErrorBanner(null);
    try {
      const response = await analysisService.triggerAnalysis(cr.id, 10);
      queryClient.invalidateQueries({ queryKey: ['analysis-runs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
      toast.success(
        'Impact analysis completed',
        `Run #${response.analysis_run_id} identified ${response.total_recommendations} test recommendation(s).`
      );
      navigate(`/impact-analysis?runId=${response.analysis_run_id}`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Impact analysis failed due to an unexpected error.';
      setAnalysisErrorBanner(`CR #${cr.id} (${cr.title}): ${msg}`);
      toast.error('Impact analysis failed', msg);
    } finally {
      setAnalyzingCrId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Action Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-lg font-bold text-app-text">
            Software Change Requests
          </h2>
          <p className="text-xs text-app-text-secondary">
            Submit proposed changes and launch deterministic regression impact analysis.
          </p>
        </div>
        <button
          type="button"
          disabled={projects.length === 0}
          onClick={() => {
            setEditingCr(null);
            setFormModalOpen(true);
          }}
          className="btn-primary shrink-0"
        >
          <Plus className="h-4 w-4" />
          New Change Request
        </button>
      </div>

      {/* Newly Created Banner with Quick Analyse CTA */}
      {newlyCreatedCr && (
        <div className="flex flex-col gap-3 rounded-lg border border-teal-300 bg-teal-50/80 px-4 py-3.5 dark:border-teal-800/70 dark:bg-teal-950/30 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2.5">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-teal-600 dark:text-teal-400" />
            <div>
              <p className="text-sm font-semibold text-app-text">
                CR #{newlyCreatedCr.id} created: {newlyCreatedCr.title}
              </p>
              <p className="text-xs text-app-text-secondary">
                Ready to score candidate test cases using structural modules, historical defects, executions, and RAG search.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={analyzingCrId !== null}
              onClick={() => handleAnalyzeImpact(newlyCreatedCr)}
              className="btn-primary text-xs"
            >
              {analyzingCrId === newlyCreatedCr.id ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Analyse Impact Now
            </button>
            <button
              type="button"
              onClick={() => setNewlyCreatedCr(null)}
              className="btn-secondary text-xs"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Analysis Error Alert */}
      {analysisErrorBanner && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50/80 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{analysisErrorBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setAnalysisErrorBanner(null)}
            className="text-xs font-semibold underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Filters */}
      <section className="surface-card p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-text-secondary" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search title, description, or ID..."
              className="input-field pl-9"
            />
          </div>

          <select
            aria-label="Filter change requests by project"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="input-field"
          >
            <option value="all">All Projects</option>
            {projects.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>

          <select
            aria-label="Filter change requests by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field"
          >
            <option value="all">All Statuses</option>
            <option value="submitted">Submitted</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </section>

      {changeRequestsQuery.isLoading && (
        <LoadingSkeleton rows={5} message="Loading change requests..." />
      )}

      {changeRequestsQuery.isError && (
        <ErrorState
          title="Could not load change requests"
          message={
            changeRequestsQuery.error instanceof ApiError
              ? changeRequestsQuery.error.message
              : 'Failed to retrieve change requests.'
          }
          onRetry={() => changeRequestsQuery.refetch()}
        />
      )}

      {!changeRequestsQuery.isLoading &&
        !changeRequestsQuery.isError &&
        projects.length === 0 && (
          <EmptyState
            title="Create a Project First"
            description="Change requests belong to a software project and its modules."
            action={
              <Link to="/projects" className="btn-primary">
                Go to Projects
              </Link>
            }
          />
        )}

      {!changeRequestsQuery.isLoading &&
        !changeRequestsQuery.isError &&
        projects.length > 0 &&
        filteredRequests.length === 0 && (
          <EmptyState
            title="No Change Requests Match"
            description="Submit a new change request describing code or API modifications to identify impacted regression tests."
            icon={<GitPullRequest className="h-6 w-6" />}
            action={
              <button
                type="button"
                onClick={() => {
                  setEditingCr(null);
                  setFormModalOpen(true);
                }}
                className="btn-primary"
              >
                <Plus className="h-4 w-4" />
                New Change Request
              </button>
            }
          />
        )}

      {!changeRequestsQuery.isLoading &&
        !changeRequestsQuery.isError &&
        filteredRequests.length > 0 && (
          <section className="surface-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                  <tr>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Title &amp; Summary</th>
                    <th className="px-4 py-3">Project</th>
                    <th className="px-4 py-3">Affected Modules</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-app-border">
                  {filteredRequests.map((cr) => {
                    const isThisAnalyzing = analyzingCrId === cr.id;
                    return (
                      <tr key={cr.id} className="hover:bg-app-muted/30">
                        <td className="px-4 py-3.5 align-top font-mono text-xs font-semibold text-app-text-secondary">
                          CR-{cr.id}
                        </td>
                        <td className="max-w-md px-4 py-3.5 align-top">
                          <p className="font-semibold text-app-text">{cr.title}</p>
                          <p className="mt-1 line-clamp-2 text-xs text-app-text-secondary">
                            {cr.description}
                          </p>
                        </td>
                        <td className="px-4 py-3.5 align-top text-xs font-medium text-app-text">
                          {projectNameById.get(cr.project_id) ?? `Project #${cr.project_id}`}
                        </td>
                        <td className="px-4 py-3.5 align-top">
                          <div className="flex flex-wrap gap-1">
                            {cr.module_ids.map((mid) => (
                              <span
                                key={mid}
                                className="rounded bg-app-muted px-2 py-0.5 text-[11px] font-medium text-app-text-secondary"
                              >
                                {moduleNameById.get(mid) ?? `Module #${mid}`}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3.5 align-top">
                          <StatusBadge value={cr.status} />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5 align-top text-xs text-app-text-secondary">
                          {formatDateTime(cr.created_at)}
                        </td>
                        <td className="px-5 py-3.5 align-top text-right">
                          <div className="inline-flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              disabled={analyzingCrId !== null}
                              onClick={() => handleAnalyzeImpact(cr)}
                              className="btn-primary px-3 py-1.5 text-xs"
                            >
                              {isThisAnalyzing ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Activity className="h-3.5 w-3.5" />
                              )}
                              {isThisAnalyzing ? 'Analyzing...' : 'Analyse Impact'}
                            </button>
                            <button
                              type="button"
                              disabled={analyzingCrId !== null}
                              onClick={() => {
                                setEditingCr(cr);
                                setFormModalOpen(true);
                              }}
                              aria-label={`Edit change request ${cr.title}`}
                              className="rounded-md p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
                            >
                              <Edit3 className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              disabled={analyzingCrId !== null}
                              onClick={() => setDeleteTarget(cr)}
                              aria-label={`Delete change request ${cr.title}`}
                              className="rounded-md p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

      <ChangeRequestFormModal
        isOpen={formModalOpen}
        onClose={() => {
          setFormModalOpen(false);
          setEditingCr(null);
        }}
        projects={projects}
        defaultProjectId={
          projectFilter !== 'all' ? Number(projectFilter) : projects[0]?.id ?? null
        }
        initialChangeRequest={editingCr}
        onSubmit={async (values) => {
          await saveMutation.mutateAsync(values);
        }}
        isSubmitting={saveMutation.isPending}
      />

      <ConfirmModal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget);
        }}
        title={deleteTarget ? `Delete CR #${deleteTarget.id}?` : 'Delete Change Request'}
        message={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.title}"? Historical analysis run logs are preserved safely.`
            : ''
        }
        confirmLabel="Delete"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />
    </div>
  );
};

