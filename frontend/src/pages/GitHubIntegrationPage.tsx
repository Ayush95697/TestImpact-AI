import React, { FormEvent, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ExternalLink,
  Github,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { ApiError } from '../services/api';
import { githubService } from '../services/githubService';
import { systemService } from '../services/systemService';
import { useToast } from '../contexts/ToastContext';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';
import { formatDateTime } from '../utils/formatters';
import type {
  AnalyzePullRequestResponse,
  ImportedPullRequest,
  Repository,
  RepositoryCreate,
} from '../types/api';

interface FormErrors {
  owner?: string;
  name?: string;
  url?: string;
  default_branch?: string;
  provider?: string;
  repository?: string;
  pr_number?: string;
}

export const GitHubIntegrationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [selectedRepository, setSelectedRepository] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Repository | null>(null);
  const [prNumber, setPrNumber] = useState('');
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalyzePullRequestResponse | null>(null);
  const [importedPullRequest, setImportedPullRequest] = useState<ImportedPullRequest | null>(null);
  const [fileFilter, setFileFilter] = useState('');
  const [registration, setRegistration] = useState<RepositoryCreate>({
    owner: '',
    name: '',
    url: '',
    default_branch: 'main',
    provider: 'github_cloud',
  });

  const healthQuery = useQuery({
    queryKey: ['github', 'health'],
    queryFn: systemService.getHealth,
    retry: 1,
  });

  const connectionQuery = useQuery({
    queryKey: ['github', 'connection', selectedRepository || null],
    queryFn: () => githubService.checkConnection(selectedRepository || undefined),
    enabled: healthQuery.isSuccess,
    retry: false,
  });

  const repositoriesQuery = useQuery({
    queryKey: ['github', 'repositories'],
    queryFn: githubService.listRepositories,
  });

  const repositories = repositoriesQuery.data ?? [];

  const registerMutation = useMutation({
    mutationFn: githubService.createRepository,
    onSuccess: (repository) => {
      queryClient.invalidateQueries({ queryKey: ['github', 'repositories'] });
      setSelectedRepository(repository.full_name);
      setRegistration({ owner: '', name: '', url: '', default_branch: 'main', provider: 'github_cloud' });
      setFormErrors({});
      toast.success('Repository registered', `${repository.full_name} is ready for analysis.`);
    },
    onError: (error) => {
      toast.error(
        'Could not register repository',
        error instanceof ApiError ? error.message : 'Registration failed.'
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (repository: Repository) => githubService.deleteRepository(repository.id),
    onSuccess: (_, repository) => {
      queryClient.invalidateQueries({ queryKey: ['github', 'repositories'] });
      queryClient.invalidateQueries({ queryKey: ['github', 'connection'] });
      if (selectedRepository === repository.full_name) {
        setSelectedRepository('');
        setPrNumber('');
        setAnalysisError(null);
      }
      if (analysisResult?.repository === repository.full_name) {
        setAnalysisResult(null);
        setImportedPullRequest(null);
        setFileFilter('');
      }
      setDeleteTarget(null);
      toast.success('Repository deleted', `${repository.full_name} was removed from TestImpact AI.`);
    },
    onError: (error) => {
      toast.error(
        'Could not delete repository',
        error instanceof ApiError ? error.message : 'Deletion failed.'
      );
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: githubService.analyzePullRequest,
    onSuccess: async (result) => {
      setAnalysisResult(result);
      setAnalysisError(null);
      const repository = repositories.find((item) => item.full_name === result.repository);
      if (repository) {
        try {
          const imported = await githubService.getImportedPullRequest(repository.id, result.pr_number);
          setImportedPullRequest(imported);
        } catch (error) {
          setImportedPullRequest(null);
          toast.warning(
            'Analysis completed',
            error instanceof ApiError ? error.message : 'Imported pull request details could not be loaded.'
          );
        }
      }
      toast.success('Pull request analyzed', `Job ${result.analysis_job_id} is ready.`);
    },
    onError: (error) => {
      setImportedPullRequest(null);
      setAnalysisResult(null);
      setAnalysisError(error instanceof ApiError ? error.message : 'Pull request analysis failed.');
    },
  });

  const validateRegistration = (): FormErrors => {
    const errors: FormErrors = {};
    const owner = registration.owner.trim();
    const name = registration.name.trim();
    const url = registration.url.trim();
    if (!owner) errors.owner = 'Owner is required.';
    if (!name) errors.name = 'Repository name is required.';
    if (!url) {
      errors.url = 'Repository URL is required.';
    } else {
      try {
        const parsed = new URL(url);
        if (!/^https?:$/.test(parsed.protocol)) errors.url = 'Use an HTTP or HTTPS URL.';
        if (parsed.username || parsed.password || parsed.search || parsed.hash) {
          errors.url = 'Do not include credentials, query parameters, or fragments.';
        }
      } catch {
        errors.url = 'Enter a valid repository URL.';
      }
    }
    if (!registration.default_branch.trim()) errors.default_branch = 'Default branch is required.';
    return errors;
  };

  const submitRegistration = (event: FormEvent) => {
    event.preventDefault();
    const errors = validateRegistration();
    setFormErrors(errors);
    if (Object.keys(errors).length) return;
    registerMutation.mutate({
      ...registration,
      owner: registration.owner.trim(),
      name: registration.name.trim(),
      url: registration.url.trim(),
      default_branch: registration.default_branch.trim(),
    });
  };

  const submitAnalysis = (event: FormEvent) => {
    event.preventDefault();
    const errors: FormErrors = {};
    if (!selectedRepository) errors.repository = 'Select a registered repository.';
    const pr = Number(prNumber);
    if (!prNumber.trim()) {
      errors.pr_number = 'Pull request number is required.';
    } else if (!Number.isInteger(pr) || pr <= 0) {
      errors.pr_number = 'Enter a positive integer.';
    }
    setFormErrors(errors);
    setAnalysisError(null);
    if (Object.keys(errors).length) return;
    analyzeMutation.mutate({ repository: selectedRepository, pr_number: pr });
  };

  const healthStatus = healthQuery.isLoading
    ? 'Checking'
    : healthQuery.isSuccess
      ? 'Connected'
      : 'Unavailable';

  const connectionStatus = connectionQuery.isLoading
    ? 'Checking'
    : connectionQuery.isSuccess
      ? 'Connected'
      : 'Unavailable';

  const filteredFiles = useMemo(() => {
    if (!importedPullRequest) return [];
    const query = fileFilter.trim().toLowerCase();
    if (!query) return importedPullRequest.changed_files;
    return importedPullRequest.changed_files.filter((file) =>
      file.file_path.toLowerCase().includes(query)
    );
  }, [fileFilter, importedPullRequest]);

  const summary = useMemo(() => {
    if (!importedPullRequest) return null;
    return importedPullRequest.changed_files.reduce(
      (result, file) => ({
        additions: result.additions + file.lines_added,
        deletions: result.deletions + file.lines_deleted,
        changedFiles: result.changedFiles + 1,
      }),
      { additions: 0, deletions: 0, changedFiles: 0 }
    );
  }, [importedPullRequest]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-heading text-xl font-bold text-app-text">Repository & Pull Request Analysis</h2>
        <p className="mt-1 max-w-3xl text-sm text-app-text-secondary">
          Register a GitHub repository, verify backend access, and import real pull request data for impact analysis.
        </p>
      </div>

      <section className="surface-card p-5" aria-labelledby="backend-status-heading">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 id="backend-status-heading" className="text-sm font-bold text-app-text">Backend connection</h3>
            <p className="mt-1 text-xs text-app-text-secondary">FastAPI health does not verify GitHub credentials.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusIndicator label="Backend API" status={healthStatus} />
            <StatusIndicator label="GitHub auth" status={connectionStatus} />
          </div>
        </div>
        {connectionQuery.isSuccess && (
          <p className="mt-3 text-xs text-app-text-secondary">
            Connected as <span className="font-mono text-app-text">{connectionQuery.data.login}</span>
          </p>
        )}
        {(healthQuery.isError || connectionQuery.isError) && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {healthQuery.isError
              ? 'The FastAPI backend is unavailable.'
              : connectionQuery.error instanceof ApiError
                ? connectionQuery.error.message
                : 'GitHub authentication could not be verified.'}
          </p>
        )}
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="surface-card p-5" aria-labelledby="register-heading">
          <h3 id="register-heading" className="text-sm font-bold text-app-text">Register repository</h3>
          <form className="mt-4 space-y-4" onSubmit={submitRegistration} noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Owner" error={formErrors.owner}>
                <input className="input-field" value={registration.owner} onChange={(event) => setRegistration({ ...registration, owner: event.target.value })} placeholder="octocat" />
              </Field>
              <Field label="Repository name" error={formErrors.name}>
                <input className="input-field" value={registration.name} onChange={(event) => setRegistration({ ...registration, name: event.target.value })} placeholder="hello-world" />
              </Field>
            </div>
            <Field label="Repository URL" error={formErrors.url}>
              <input className="input-field" value={registration.url} onChange={(event) => setRegistration({ ...registration, url: event.target.value })} placeholder="https://github.com/octocat/hello-world" />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Default branch" error={formErrors.default_branch}>
                <input className="input-field" value={registration.default_branch} onChange={(event) => setRegistration({ ...registration, default_branch: event.target.value })} />
              </Field>
              <Field label="Provider" error={formErrors.provider}>
                <select className="input-field" value={registration.provider} onChange={(event) => setRegistration({ ...registration, provider: event.target.value as RepositoryCreate['provider'] })}>
                  <option value="github_cloud">GitHub Cloud</option>
                  <option value="github_enterprise">GitHub Enterprise</option>
                </select>
              </Field>
            </div>
            <button type="submit" className="btn-primary" disabled={registerMutation.isPending}>
              {registerMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Github className="h-4 w-4" />}
              {registerMutation.isPending ? 'Registering...' : 'Register repository'}
            </button>
          </form>
        </section>

        <section className="surface-card p-5" aria-labelledby="repositories-heading">
          <div className="flex items-center justify-between gap-3">
            <h3 id="repositories-heading" className="text-sm font-bold text-app-text">Registered repositories</h3>
            <button type="button" className="btn-secondary px-2.5" onClick={() => repositoriesQuery.refetch()} disabled={repositoriesQuery.isFetching}>
              <RefreshCw className={`h-4 w-4 ${repositoriesQuery.isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          <div className="mt-4">
            {repositoriesQuery.isLoading ? (
              <LoadingSkeleton rows={3} message="Loading repositories..." />
            ) : repositoriesQuery.isError ? (
              <ErrorState message={repositoriesQuery.error instanceof ApiError ? repositoriesQuery.error.message : 'Unable to load repositories.'} onRetry={() => repositoriesQuery.refetch()} />
            ) : repositories.length === 0 ? (
              <EmptyState title="No repositories registered" description="Register the first repository to begin pull request analysis." />
            ) : (
              <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                {repositories.map((repository) => (
                  <RepositoryRow
                    key={repository.id}
                    repository={repository}
                    selected={selectedRepository === repository.full_name}
                    onSelect={() => setSelectedRepository(repository.full_name)}
                    onDelete={() => setDeleteTarget(repository)}
                    deleteDisabled={deleteMutation.isPending}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="surface-card p-5" aria-labelledby="analyze-heading">
        <h3 id="analyze-heading" className="text-sm font-bold text-app-text">Analyze pull request</h3>
        <form className="mt-4 grid gap-4 md:grid-cols-[minmax(240px,1fr)_220px_auto] md:items-end" onSubmit={submitAnalysis} noValidate>
          <Field label="Repository" error={formErrors.repository}>
            <select className="input-field" value={selectedRepository} onChange={(event) => setSelectedRepository(event.target.value)}>
              <option value="">Select a repository</option>
              {repositories.map((repository) => (
                <option key={repository.id} value={repository.full_name}>{repository.full_name}</option>
              ))}
            </select>
          </Field>
          <Field label="Pull request number" error={formErrors.pr_number}>
            <input className="input-field" inputMode="numeric" value={prNumber} onChange={(event) => setPrNumber(event.target.value)} placeholder="123" />
          </Field>
          <button type="submit" className="btn-primary md:mb-px" disabled={analyzeMutation.isPending}>
            {analyzeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {analyzeMutation.isPending ? 'Retrieving pull request from GitHub...' : 'Analyze Pull Request'}
          </button>
        </form>
        {analysisError && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300" role="alert">
            {analysisError}
          </div>
        )}
      </section>

      {(analysisResult || importedPullRequest) && (
        <section className="surface-card p-5" aria-labelledby="result-heading">
          <h3 id="result-heading" className="text-sm font-bold text-app-text">Analysis result</h3>
          {analysisResult && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <ResultItem label="Repository" value={analysisResult.repository} />
              <ResultItem label="PR number" value={`#${analysisResult.pr_number}`} />
              <ResultItem label="Job ID" value={analysisResult.analysis_job_id} mono />
              <ResultItem label="Status" value={analysisResult.status} />
            </div>
          )}

          {importedPullRequest && (
            <>
              <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <ResultItem label="Title" value={importedPullRequest.title} />
                <ResultItem label="State" value={importedPullRequest.status} />
                <ResultItem label="Author" value={importedPullRequest.author ?? 'Not provided'} />
                <ResultItem label="Created" value={formatDateTime(importedPullRequest.created_at)} />
                <ResultItem label="Base branch" value={importedPullRequest.base_branch} mono />
                <ResultItem label="Head branch" value={importedPullRequest.head_branch} mono />
                {importedPullRequest.merged_at && <ResultItem label="Merged" value={formatDateTime(importedPullRequest.merged_at)} />}
              </div>
              {importedPullRequest.description && (
                <div className="mt-4">
                  <p className="field-label">Description</p>
                  <p className="whitespace-pre-wrap rounded-md border border-app-border bg-app-muted/40 p-3 text-sm text-app-text-secondary">{importedPullRequest.description}</p>
                </div>
              )}
              {summary && (
                <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <SummaryItem label="Commits" value={importedPullRequest.commits.length} />
                  <SummaryItem label="Changed files" value={summary.changedFiles} />
                  <SummaryItem label="Additions" value={summary.additions} positive />
                  <SummaryItem label="Deletions" value={summary.deletions} />
                </div>
              )}

              <div className="mt-6">
                <h4 className="text-sm font-bold text-app-text">Commits</h4>
                {importedPullRequest.commits.length ? (
                  <div className="mt-3 space-y-2">
                    {importedPullRequest.commits.map((sha) => (
                      <code key={sha} className="block rounded-md border border-app-border bg-app-muted/40 px-3 py-2 text-xs text-app-text">{sha}</code>
                    ))}
                  </div>
                ) : <p className="mt-2 text-sm text-app-text-secondary">No commits returned.</p>}
              </div>

              <div className="mt-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <h4 className="text-sm font-bold text-app-text">Changed files</h4>
                  <label className="relative block sm:w-72">
                    <span className="sr-only">Filter changed files</span>
                    <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-app-text-secondary" />
                    <input className="input-field pl-9" value={fileFilter} onChange={(event) => setFileFilter(event.target.value)} placeholder="Filter file paths" />
                  </label>
                </div>
                {filteredFiles.length ? (
                  <div className="mt-3 grid gap-2">
                    {filteredFiles.map((file) => (
                      <div key={file.file_path} className="rounded-md border border-app-border p-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <code className="min-w-0 break-all text-xs font-medium text-app-text">{file.file_path}</code>
                          <div className="flex gap-2 text-xs">
                            <span className="rounded bg-app-muted px-2 py-1 text-app-text-secondary">{file.change_type}</span>
                            <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">+{file.lines_added}</span>
                            <span className="rounded bg-red-50 px-2 py-1 text-red-700 dark:bg-red-950/40 dark:text-red-300">-{file.lines_deleted}</span>
                          </div>
                        </div>
                        {file.previous_filename && <p className="mt-2 text-xs text-app-text-secondary">Previous: {file.previous_filename}</p>}
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-3 text-sm text-app-text-secondary">No changed files match the filter.</p>}
              </div>

              {importedPullRequest.diff && (
                <div className="mt-6">
                  <h4 className="text-sm font-bold text-app-text">Diff preview</h4>
                  <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-app-border bg-slate-950 p-4 text-xs leading-relaxed text-slate-200">
                    {importedPullRequest.diff}
                  </pre>
                </div>
              )}
            </>
          )}
        </section>
      )}

      <ConfirmModal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget);
        }}
        title={deleteTarget ? `Delete ${deleteTarget.full_name}?` : 'Delete repository'}
        message={
          deleteTarget
            ? `This removes ${deleteTarget.full_name} and its imported pull request data from TestImpact AI. The repository on GitHub will not be affected.`
            : ''
        }
        confirmLabel="Delete repository"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />
    </div>
  );
};

const StatusIndicator: React.FC<{ label: string; status: 'Checking' | 'Connected' | 'Unavailable' }> = ({ label, status }) => (
  <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
    status === 'Connected'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300'
      : status === 'Unavailable'
        ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300'
        : 'border-app-border bg-app-muted text-app-text-secondary'
  }`}>
    <span className={`h-2 w-2 rounded-full ${status === 'Connected' ? 'bg-emerald-500' : status === 'Unavailable' ? 'bg-red-500' : 'animate-pulse bg-slate-400'}`} />
    {label}: {status}
  </div>
);

const Field: React.FC<{ label: string; error?: string; children: React.ReactNode }> = ({ label, error, children }) => (
  <label className="block">
    <span className="field-label">{label}</span>
    {children}
    {error && <span className="mt-1 block text-xs font-medium text-red-600 dark:text-red-400">{error}</span>}
  </label>
);

const RepositoryRow: React.FC<{
  repository: Repository;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  deleteDisabled: boolean;
}> = ({ repository, selected, onSelect, onDelete, deleteDisabled }) => (
  <div className={`rounded-md border p-3 ${selected ? 'border-indigo-500 bg-indigo-50/60 dark:bg-indigo-950/20' : 'border-app-border bg-app-surface'}`}>
    <div className="flex items-start justify-between gap-3">
      <button type="button" className="min-w-0 text-left" onClick={onSelect}>
        <span className="block truncate text-sm font-semibold text-app-text">{repository.full_name}</span>
        <span className="mt-1 block text-xs text-app-text-secondary">ID {repository.id} · {repository.provider} · {repository.default_branch}</span>
        <span className="mt-1 block text-xs text-app-text-secondary">{formatDateTime(repository.created_at)}</span>
      </button>
      <div className="flex shrink-0 items-center gap-1">
        {repository.url && (
          <a href={repository.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${repository.full_name} on GitHub`} className="rounded p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text">
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
        <button
          type="button"
          onClick={onDelete}
          disabled={deleteDisabled}
          aria-label={`Delete ${repository.full_name}`}
          title="Delete repository"
          className="rounded p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-red-950/40 dark:hover:text-red-400"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  </div>
);

const ResultItem: React.FC<{ label: string; value: string; mono?: boolean }> = ({ label, value, mono }) => (
  <div className="rounded-md border border-app-border bg-app-muted/40 p-3">
    <p className="text-xs font-semibold uppercase tracking-wide text-app-text-secondary">{label}</p>
    <p className={`mt-1 break-words text-sm text-app-text ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
  </div>
);

const SummaryItem: React.FC<{ label: string; value: number; positive?: boolean }> = ({ label, value, positive }) => (
  <div className="rounded-md border border-app-border p-3 text-center">
    <p className="text-xs text-app-text-secondary">{label}</p>
    <p className={`mt-1 text-lg font-bold ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-app-text'}`}>{value}</p>
  </div>
);
