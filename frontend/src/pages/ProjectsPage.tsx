import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Boxes,
  Bug,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Database,
  Edit3,
  FolderKanban,
  History as HistoryIcon,
  Info,
  Loader2,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import { projectService } from '../services/projectService';
import { moduleService } from '../services/moduleService';
import { testCaseService } from '../services/testCaseService';
import { defectService } from '../services/defectService';
import { testExecutionService } from '../services/testExecutionService';
import { systemService } from '../services/systemService';
import { ragService } from '../services/ragService';
import { ApiError } from '../services/api';
import { useSystemCapabilities } from '../hooks/useSystemStatus';
import { useToast } from '../contexts/ToastContext';
import { formatDateTime, formatShortDate } from '../utils/formatters';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/common/StateViews';
import { ProjectFormModal } from '../components/projects/ProjectFormModal';
import { ModuleFormModal } from '../components/projects/ModuleFormModal';
import { TestCaseFormModal } from '../components/projects/TestCaseFormModal';
import { DefectFormModal } from '../components/projects/DefectFormModal';
import { ExecutionFormModal } from '../components/projects/ExecutionFormModal';
import type {
  Defect,
  ExecutionStatus,
  ModuleItem,
  Project,
  TestCase,
} from '../types/api';

type ProjectTab = 'overview' | 'modules' | 'test-cases' | 'defects' | 'executions';

type DeleteTarget =
  | { kind: 'project'; item: Project }
  | { kind: 'module'; item: ModuleItem }
  | { kind: 'testCase'; item: TestCase }
  | { kind: 'defect'; item: Defect };

export const ProjectsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const capabilitiesQuery = useSystemCapabilities();
  const capabilities = capabilitiesQuery.data;

  const [activeTab, setActiveTab] = useState<ProjectTab>('overview');
  const [projectSearch, setProjectSearch] = useState('');

  // Modals state
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const [moduleModalOpen, setModuleModalOpen] = useState(false);
  const [editingModule, setEditingModule] = useState<ModuleItem | null>(null);

  const [testCaseModalOpen, setTestCaseModalOpen] = useState(false);
  const [editingTestCase, setEditingTestCase] = useState<TestCase | null>(null);
  const [expandedTestCaseId, setExpandedTestCaseId] = useState<number | null>(null);

  const [defectModalOpen, setDefectModalOpen] = useState(false);
  const [editingDefect, setEditingDefect] = useState<Defect | null>(null);

  const [execModalOpen, setExecModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);

  // Filters within project tabs
  const [moduleFilter, setModuleFilter] = useState('');
  const [tcModuleFilter, setTcModuleFilter] = useState<string>('all');
  const [tcPriorityFilter, setTcPriorityFilter] = useState<string>('all');
  const [defectModuleFilter, setDefectModuleFilter] = useState<string>('all');
  const [defectSeverityFilter, setDefectSeverityFilter] = useState<string>('all');
  const [execTcFilter, setExecTcFilter] = useState<string>('all');
  const [execStatusFilter, setExecStatusFilter] = useState<string>('all');

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectService.listProjects(),
  });

  const dashboardSummaryQuery = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => systemService.getDashboardSummary(),
  });

  const projects = projectsQuery.data ?? [];
  const overviewById = useMemo(() => {
    const map = new Map<
      number,
      { module_count: number; test_case_count: number; defect_count: number; change_request_count: number }
    >();
    for (const item of dashboardSummaryQuery.data?.projects_overview ?? []) {
      map.set(item.id, item);
    }
    return map;
  }, [dashboardSummaryQuery.data]);

  const requestedProjectId = Number(searchParams.get('projectId'));
  const selectedProject = useMemo(() => {
    if (projects.length === 0) return null;
    if (Number.isFinite(requestedProjectId) && requestedProjectId > 0) {
      const found = projects.find((p) => p.id === requestedProjectId);
      if (found) return found;
    }
    return projects[0];
  }, [projects, requestedProjectId]);

  const selectedProjectId = selectedProject?.id ?? null;

  useEffect(() => {
    setExpandedTestCaseId(null);
    setTcModuleFilter('all');
    setTcPriorityFilter('all');
    setDefectModuleFilter('all');
    setDefectSeverityFilter('all');
    setExecTcFilter('all');
    setExecStatusFilter('all');
  }, [selectedProjectId]);

  const selectProject = (projectId: number) => {
    setSearchParams({ projectId: String(projectId) });
  };

  const modulesQuery = useQuery({
    queryKey: ['projects', selectedProjectId, 'modules'],
    queryFn: () => moduleService.listByProject(selectedProjectId!),
    enabled: selectedProjectId !== null,
  });

  const testCasesQuery = useQuery({
    queryKey: ['test-cases', { project_id: selectedProjectId }],
    queryFn: () => testCaseService.listTestCases({ project_id: selectedProjectId! }),
    enabled: selectedProjectId !== null,
  });

  const defectsQuery = useQuery({
    queryKey: ['defects', { project_id: selectedProjectId }],
    queryFn: () => defectService.listDefects({ project_id: selectedProjectId! }),
    enabled: selectedProjectId !== null,
  });

  const executionsQuery = useQuery({
    queryKey: ['test-executions', { project_id: selectedProjectId }],
    queryFn: () => testExecutionService.listExecutions({ project_id: selectedProjectId! }),
    enabled: selectedProjectId !== null,
  });

  const modules = modulesQuery.data ?? [];
  const testCases = testCasesQuery.data ?? [];
  const defects = defectsQuery.data ?? [];
  const executions = executionsQuery.data ?? [];

  const moduleNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const m of modules) map.set(m.id, m.name);
    return map;
  }, [modules]);

  const testCaseTitleById = useMemo(() => {
    const map = new Map<number, string>();
    for (const tc of testCases) map.set(tc.id, tc.title);
    return map;
  }, [testCases]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.description ?? '').toLowerCase().includes(q) ||
        String(p.id).includes(q)
    );
  }, [projects, projectSearch]);

  const invalidateProjectScope = (projectId?: number) => {
    queryClient.invalidateQueries({ queryKey: ['projects'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
    if (projectId) {
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'modules'] });
      queryClient.invalidateQueries({ queryKey: ['test-cases', { project_id: projectId }] });
      queryClient.invalidateQueries({ queryKey: ['defects', { project_id: projectId }] });
      queryClient.invalidateQueries({ queryKey: ['test-executions', { project_id: projectId }] });
    }
  };

  // Mutations
  const saveProjectMutation = useMutation({
    mutationFn: async (values: { name: string; description: string | null }) => {
      if (editingProject) {
        return projectService.updateProject(editingProject.id, values);
      }
      return projectService.createProject(values);
    },
    onSuccess: (saved) => {
      invalidateProjectScope(saved.id);
      setProjectModalOpen(false);
      setEditingProject(null);
      selectProject(saved.id);
      toast.success(
        editingProject ? 'Project updated' : 'Project created',
        `"${saved.name}" saved successfully.`
      );
    },
    onError: (err) => {
      toast.error(
        'Project save failed',
        err instanceof ApiError ? err.message : 'Unable to save project'
      );
    },
  });

  const saveModuleMutation = useMutation({
    mutationFn: async (values: { name: string; description: string | null }) => {
      if (editingModule) {
        return moduleService.updateModule(editingModule.id, values);
      }
      return moduleService.createModule(selectedProjectId!, values);
    },
    onSuccess: (saved) => {
      invalidateProjectScope(selectedProjectId ?? undefined);
      setModuleModalOpen(false);
      setEditingModule(null);
      toast.success(
        editingModule ? 'Module updated' : 'Module created',
        `Module "${saved.name}" saved.`
      );
    },
    onError: (err) => {
      toast.error(
        'Module action failed',
        err instanceof ApiError ? err.message : 'Unable to save module'
      );
    },
  });

  const saveTestCaseMutation = useMutation({
    mutationFn: async (values: {
      title: string;
      priority: string;
      steps: string;
      expected_result: string;
      module_ids: number[];
    }) => {
      if (editingTestCase) {
        return testCaseService.updateTestCase(editingTestCase.id, values);
      }
      return testCaseService.createTestCase({
        project_id: selectedProjectId!,
        ...values,
      });
    },
    onSuccess: (saved) => {
      invalidateProjectScope(selectedProjectId ?? undefined);
      setTestCaseModalOpen(false);
      setEditingTestCase(null);
      toast.success(
        editingTestCase ? 'Test case updated' : 'Test case created',
        `"${saved.title}" saved.`
      );
    },
    onError: (err) => {
      toast.error(
        'Test case action failed',
        err instanceof ApiError ? err.message : 'Unable to save test case'
      );
    },
  });

  const saveDefectMutation = useMutation({
    mutationFn: async (values: {
      title: string;
      module_id: number;
      severity: string;
      description: string;
      resolution_notes: string | null;
    }) => {
      if (editingDefect) {
        return defectService.updateDefect(editingDefect.id, {
          title: values.title,
          severity: values.severity,
          description: values.description,
          resolution_notes: values.resolution_notes,
        });
      }
      return defectService.createDefect({
        project_id: selectedProjectId!,
        ...values,
      });
    },
    onSuccess: (saved) => {
      invalidateProjectScope(selectedProjectId ?? undefined);
      setDefectModalOpen(false);
      setEditingDefect(null);
      toast.success(
        editingDefect ? 'Defect updated' : 'Defect logged',
        `"${saved.title}" saved.`
      );
    },
    onError: (err) => {
      toast.error(
        'Defect action failed',
        err instanceof ApiError ? err.message : 'Unable to save defect'
      );
    },
  });

  const createExecMutation = useMutation({
    mutationFn: (values: {
      test_case_id: number;
      status: ExecutionStatus;
      build_version: string | null;
    }) => testExecutionService.createExecution(values),
    onSuccess: () => {
      invalidateProjectScope(selectedProjectId ?? undefined);
      setExecModalOpen(false);
      toast.success('Execution recorded', 'Historical test execution logged successfully.');
    },
    onError: (err) => {
      toast.error(
        'Execution failed',
        err instanceof ApiError ? err.message : 'Unable to log test execution'
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (target: DeleteTarget) => {
      switch (target.kind) {
        case 'project':
          await projectService.deleteProject(target.item.id);
          return target.item.name;
        case 'module':
          await moduleService.deleteModule(target.item.id);
          return target.item.name;
        case 'testCase':
          await testCaseService.deleteTestCase(target.item.id);
          return target.item.title;
        case 'defect':
          await defectService.deleteDefect(target.item.id);
          return target.item.title;
      }
    },
    onSuccess: (name, target) => {
      if (target.kind === 'project') {
        setSearchParams({});
        invalidateProjectScope();
      } else {
        invalidateProjectScope(selectedProjectId ?? undefined);
      }
      setDeleteTarget(null);
      toast.success('Deleted successfully', `"${name}" was removed.`);
    },
    onError: (err) => {
      const apiErr = err instanceof ApiError ? err : null;
      setDeleteTarget(null);
      toast.error(
        apiErr?.status === 409 ? 'Deletion blocked by integrity rules' : 'Delete failed',
        apiErr?.message ?? 'Unable to delete selected record.'
      );
    },
  });

  const indexRagMutation = useMutation({
    mutationFn: (projectId: number) => ragService.indexProject(projectId),
    onSuccess: (res) => {
      toast.success(
        'Vector knowledge base indexed',
        `Indexed ${res.total_indexed} document(s) (${res.test_cases_indexed} test cases, ${res.defects_indexed} defects, ${res.test_executions_indexed} executions).`
      );
    },
    onError: (err) => {
      toast.error(
        'Vector indexing unavailable',
        err instanceof ApiError ? err.message : 'Failed to index project records.'
      );
    },
  });

  // Filtered tab data
  const filteredModules = useMemo(() => {
    const q = moduleFilter.trim().toLowerCase();
    if (!q) return modules;
    return modules.filter(
      (m) => m.name.toLowerCase().includes(q) || (m.description ?? '').toLowerCase().includes(q)
    );
  }, [modules, moduleFilter]);

  const filteredTestCases = useMemo(() => {
    return testCases.filter((tc) => {
      if (tcModuleFilter !== 'all' && !tc.module_ids.includes(Number(tcModuleFilter))) {
        return false;
      }
      if (tcPriorityFilter !== 'all' && tc.priority.toLowerCase() !== tcPriorityFilter) {
        return false;
      }
      return true;
    });
  }, [testCases, tcModuleFilter, tcPriorityFilter]);

  const filteredDefects = useMemo(() => {
    return defects.filter((d) => {
      if (defectModuleFilter !== 'all' && d.module_id !== Number(defectModuleFilter)) {
        return false;
      }
      if (defectSeverityFilter !== 'all' && d.severity.toLowerCase() !== defectSeverityFilter) {
        return false;
      }
      return true;
    });
  }, [defects, defectModuleFilter, defectSeverityFilter]);

  const filteredExecutions = useMemo(() => {
    return executions.filter((ex) => {
      if (execTcFilter !== 'all' && ex.test_case_id !== Number(execTcFilter)) {
        return false;
      }
      if (execStatusFilter !== 'all' && ex.status.toLowerCase() !== execStatusFilter) {
        return false;
      }
      return true;
    });
  }, [executions, execTcFilter, execStatusFilter]);

  const tabs: Array<{ id: ProjectTab; label: string; count?: number; icon: React.FC<{ className?: string }> }> = [
    { id: 'overview', label: 'Overview', icon: Info },
    { id: 'modules', label: 'Modules', count: modules.length, icon: Boxes },
    { id: 'test-cases', label: 'Test Cases', count: testCases.length, icon: ClipboardCheck },
    { id: 'defects', label: 'Defects', count: defects.length, icon: Bug },
    { id: 'executions', label: 'Test Executions', count: executions.length, icon: HistoryIcon },
  ];

  const deleteConfirmInfo = useMemo(() => {
    if (!deleteTarget) return { title: '', message: '' };
    switch (deleteTarget.kind) {
      case 'project':
        return {
          title: `Delete Project "${deleteTarget.item.name}"?`,
          message:
            'Only empty projects without modules, test cases, defects, or change requests can be deleted. Associated items will block deletion (HTTP 409).',
        };
      case 'module':
        return {
          title: `Delete Module "${deleteTarget.item.name}"?`,
          message:
            'Modules linked to existing test cases, defects, or change requests cannot be deleted until unlinked.',
        };
      case 'testCase':
        return {
          title: `Delete Test Case "${deleteTarget.item.title}"?`,
          message:
            'Test cases with historical execution records are protected from deletion (HTTP 409) to preserve audit integrity.',
        };
      case 'defect':
        return {
          title: `Delete Defect "${deleteTarget.item.title}"?`,
          message: 'This defect record will be permanently removed from the project.',
        };
    }
  }, [deleteTarget]);

  return (
    <div className="space-y-6">
      {/* Top Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-lg font-bold text-app-text">
            Project Repositories & Test Assets
          </h2>
          <p className="text-xs text-app-text-secondary">
            Manage software projects, architectural modules, test suites, defect logs, and run histories.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditingProject(null);
            setProjectModalOpen(true);
          }}
          className="btn-primary shrink-0"
        >
          <Plus className="h-4 w-4" />
          Create Project
        </button>
      </div>

      {projectsQuery.isLoading && (
        <LoadingSkeleton rows={5} message="Loading projects from FastAPI..." />
      )}

      {projectsQuery.isError && (
        <ErrorState
          title="Could not load projects"
          message={
            projectsQuery.error instanceof ApiError
              ? projectsQuery.error.message
              : 'Failed to retrieve projects.'
          }
          onRetry={() => projectsQuery.refetch()}
        />
      )}

      {!projectsQuery.isLoading && !projectsQuery.isError && projects.length === 0 && (
        <EmptyState
          title="No Projects Available"
          description="Create a software project first to organize its modules, regression test cases, historical defects, and change requests."
          icon={<FolderKanban className="h-6 w-6" />}
          action={
            <button
              type="button"
              onClick={() => {
                setEditingProject(null);
                setProjectModalOpen(true);
              }}
              className="btn-primary"
            >
              <Plus className="h-4 w-4" />
              Create Project
            </button>
          }
        />
      )}

      {!projectsQuery.isLoading && !projectsQuery.isError && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Column: Project Directory */}
          <section className="lg:col-span-4 space-y-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-text-secondary" />
              <input
                type="search"
                value={projectSearch}
                onChange={(e) => setProjectSearch(e.target.value)}
                placeholder="Filter projects by name or ID..."
                className="input-field pl-9"
              />
            </div>

            <div className="space-y-2.5">
              {filteredProjects.map((project) => {
                const isSelected = project.id === selectedProjectId;
                const counts = overviewById.get(project.id);
                return (
                  <div
                    key={project.id}
                    className={`surface-card cursor-pointer p-4 transition-all ${
                      isSelected
                        ? 'border-indigo-500 ring-1 ring-indigo-500/40'
                        : 'hover:border-app-border-strong'
                    }`}
                    onClick={() => selectProject(project.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-app-muted px-1.5 py-0.5 font-mono text-[11px] font-medium text-app-text-secondary">
                            #{project.id}
                          </span>
                          <h3 className="truncate text-sm font-bold text-app-text">
                            {project.name}
                          </h3>
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs text-app-text-secondary">
                          {project.description || 'No description provided.'}
                        </p>
                      </div>

                      <div
                        className="flex shrink-0 items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setEditingProject(project);
                            setProjectModalOpen(true);
                          }}
                          title="Edit project"
                          aria-label={`Edit ${project.name}`}
                          className="rounded p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget({ kind: 'project', item: project })}
                          title="Delete project"
                          aria-label={`Delete ${project.name}`}
                          className="rounded p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-app-border pt-2.5 text-xs text-app-text-secondary">
                      <div className="flex items-center gap-3 font-mono">
                        <span>{counts ? counts.module_count : '—'} modules</span>
                        <span>{counts ? counts.test_case_count : '—'} tests</span>
                      </div>
                      <span>Created {formatShortDate(project.created_at)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Right Column: Selected Project Detail Workspace */}
          {selectedProject && (
            <section className="lg:col-span-8 space-y-4">
              <div className="surface-card overflow-hidden">
                {/* Project Detail Header */}
                <div className="border-b border-app-border px-5 py-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-indigo-50 px-2 py-0.5 font-mono text-xs font-semibold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
                          Project #{selectedProject.id}
                        </span>
                        <h3 className="font-heading text-lg font-bold text-app-text">
                          {selectedProject.name}
                        </h3>
                      </div>
                      <p className="mt-1 text-sm text-app-text-secondary">
                        {selectedProject.description || 'No project description recorded.'}
                      </p>
                    </div>
                    <Link
                      to={`/change-requests?projectId=${selectedProject.id}`}
                      className="btn-secondary shrink-0 text-xs"
                    >
                      View Change Requests
                    </Link>
                  </div>

                  {/* Tab Bar */}
                  <div
                    role="tablist"
                    aria-label="Project details sections"
                    className="mt-4 flex flex-wrap gap-1 border-t border-app-border pt-3"
                  >
                    {tabs.map((tab) => {
                      const Icon = tab.icon;
                      const active = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          role="tab"
                          aria-selected={active}
                          type="button"
                          onClick={() => setActiveTab(tab.id)}
                          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                            active
                              ? 'bg-indigo-600 text-white'
                              : 'text-app-text-secondary hover:bg-app-muted hover:text-app-text'
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          <span>{tab.label}</span>
                          {tab.count !== undefined && (
                            <span
                              className={`ml-0.5 rounded-full px-1.5 py-0.2 font-mono text-[10px] ${
                                active
                                  ? 'bg-white/20 text-white'
                                  : 'bg-app-muted text-app-text-secondary'
                              }`}
                            >
                              {tab.count}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Tab Content */}
                <div className="p-5">
                  {/* TAB 1: OVERVIEW */}
                  {activeTab === 'overview' && (
                    <div className="space-y-5">
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <div className="rounded-md border border-app-border bg-app-muted/40 p-3.5">
                          <span className="text-xs text-app-text-secondary">Modules</span>
                          <p className="mt-1 font-mono text-xl font-bold text-app-text">
                            {modules.length}
                          </p>
                        </div>
                        <div className="rounded-md border border-app-border bg-app-muted/40 p-3.5">
                          <span className="text-xs text-app-text-secondary">Test Cases</span>
                          <p className="mt-1 font-mono text-xl font-bold text-app-text">
                            {testCases.length}
                          </p>
                        </div>
                        <div className="rounded-md border border-app-border bg-app-muted/40 p-3.5">
                          <span className="text-xs text-app-text-secondary">Defects</span>
                          <p className="mt-1 font-mono text-xl font-bold text-app-text">
                            {defects.length}
                          </p>
                        </div>
                        <div className="rounded-md border border-app-border bg-app-muted/40 p-3.5">
                          <span className="text-xs text-app-text-secondary">Executions</span>
                          <p className="mt-1 font-mono text-xl font-bold text-app-text">
                            {executions.length}
                          </p>
                        </div>
                      </div>

                      <div className="rounded-lg border border-app-border bg-app-muted/30 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5 rounded-md bg-teal-50 p-2 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400">
                              <Database className="h-4 w-4" />
                            </div>
                            <div>
                              <h4 className="text-sm font-bold text-app-text">
                                Semantic Vector Knowledge Base (ChromaDB)
                              </h4>
                              <p className="mt-0.5 text-xs text-app-text-secondary">
                                Index this project&apos;s test cases, defects, and execution records so
                                semantic similarity contributes up to +25 pts during impact analysis.
                              </p>
                            </div>
                          </div>

                          <button
                            type="button"
                            disabled={
                              !capabilities?.rag_available || indexRagMutation.isPending
                            }
                            onClick={() => indexRagMutation.mutate(selectedProject.id)}
                            className="btn-secondary shrink-0"
                            title={
                              capabilities?.rag_available
                                ? 'Re-index project records into ChromaDB'
                                : 'Company embedding API is not configured on backend'
                            }
                          >
                            {indexRagMutation.isPending && (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            )}
                            {capabilities?.rag_available
                              ? 'Re-index Knowledge Base'
                              : 'Embeddings Unconfigured'}
                          </button>
                        </div>
                      </div>

                      <div className="text-xs text-app-text-secondary">
                        Created on <span className="font-medium text-app-text">{formatDateTime(selectedProject.created_at)}</span>
                      </div>
                    </div>
                  )}

                  {/* TAB 2: MODULES */}
                  {activeTab === 'modules' && (
                    <div className="space-y-4">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="relative max-w-xs flex-1">
                          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-app-text-secondary" />
                          <input
                            type="search"
                            value={moduleFilter}
                            onChange={(e) => setModuleFilter(e.target.value)}
                            placeholder="Filter modules..."
                            className="input-field py-1.5 pl-8 text-xs"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingModule(null);
                            setModuleModalOpen(true);
                          }}
                          className="btn-primary text-xs"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Add Module
                        </button>
                      </div>

                      {modulesQuery.isLoading ? (
                        <LoadingSkeleton rows={3} message="Loading modules..." />
                      ) : filteredModules.length === 0 ? (
                        <EmptyState
                          title="No Modules Found"
                          description="Modules map software areas to test cases, defects, and change requests."
                        />
                      ) : (
                        <div className="overflow-x-auto rounded-md border border-app-border">
                          <table className="w-full text-left text-sm">
                            <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                              <tr>
                                <th className="px-4 py-2.5">ID</th>
                                <th className="px-4 py-2.5">Module Name</th>
                                <th className="px-4 py-2.5">Description</th>
                                <th className="px-4 py-2.5 text-right">Actions</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-app-border">
                              {filteredModules.map((mod) => (
                                <tr key={mod.id} className="hover:bg-app-muted/30">
                                  <td className="px-4 py-2.5 font-mono text-xs text-app-text-secondary">
                                    #{mod.id}
                                  </td>
                                  <td className="px-4 py-2.5 font-medium text-app-text">
                                    {mod.name}
                                  </td>
                                  <td className="px-4 py-2.5 text-xs text-app-text-secondary">
                                    {mod.description || '—'}
                                  </td>
                                  <td className="px-4 py-2.5 text-right">
                                    <div className="inline-flex items-center gap-1">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setEditingModule(mod);
                                          setModuleModalOpen(true);
                                        }}
                                        aria-label={`Edit module ${mod.name}`}
                                        className="rounded p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
                                      >
                                        <Edit3 className="h-3.5 w-3.5" />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setDeleteTarget({ kind: 'module', item: mod })
                                        }
                                        aria-label={`Delete module ${mod.name}`}
                                        className="rounded p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 3: TEST CASES */}
                  {activeTab === 'test-cases' && (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            aria-label="Filter test cases by module"
                            value={tcModuleFilter}
                            onChange={(e) => setTcModuleFilter(e.target.value)}
                            className="input-field w-auto py-1.5 text-xs"
                          >
                            <option value="all">All Modules</option>
                            {modules.map((m) => (
                              <option key={m.id} value={String(m.id)}>
                                {m.name}
                              </option>
                            ))}
                          </select>
                          <select
                            aria-label="Filter test cases by priority"
                            value={tcPriorityFilter}
                            onChange={(e) => setTcPriorityFilter(e.target.value)}
                            className="input-field w-auto py-1.5 text-xs"
                          >
                            <option value="all">All Priorities</option>
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                          </select>
                        </div>

                        <button
                          type="button"
                          disabled={modules.length === 0}
                          onClick={() => {
                            setEditingTestCase(null);
                            setTestCaseModalOpen(true);
                          }}
                          className="btn-primary text-xs"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Add Test Case
                        </button>
                      </div>

                      {testCasesQuery.isLoading ? (
                        <LoadingSkeleton rows={4} message="Loading test cases..." />
                      ) : filteredTestCases.length === 0 ? (
                        <EmptyState
                          title="No Test Cases Found"
                          description={
                            modules.length === 0
                              ? 'Add at least one module before creating test cases.'
                              : 'Create regression test cases linked to project modules.'
                          }
                        />
                      ) : (
                        <div className="overflow-x-auto rounded-md border border-app-border">
                          <table className="w-full text-left text-sm">
                            <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                              <tr>
                                <th className="w-8 px-3 py-2.5"></th>
                                <th className="px-3 py-2.5">ID</th>
                                <th className="px-3 py-2.5">Title</th>
                                <th className="px-3 py-2.5">Priority</th>
                                <th className="px-3 py-2.5">Modules</th>
                                <th className="px-4 py-2.5 text-right">Actions</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-app-border">
                              {filteredTestCases.map((tc) => {
                                const expanded = expandedTestCaseId === tc.id;
                                return (
                                  <React.Fragment key={tc.id}>
                                    <tr
                                      className="cursor-pointer hover:bg-app-muted/30"
                                      onClick={() =>
                                        setExpandedTestCaseId(expanded ? null : tc.id)
                                      }
                                    >
                                      <td className="px-3 py-2.5 text-app-text-secondary">
                                        {expanded ? (
                                          <ChevronDown className="h-4 w-4" />
                                        ) : (
                                          <ChevronRight className="h-4 w-4" />
                                        )}
                                      </td>
                                      <td className="px-3 py-2.5 font-mono text-xs text-app-text-secondary">
                                        TC-{tc.id}
                                      </td>
                                      <td className="px-3 py-2.5 font-medium text-app-text">
                                        {tc.title}
                                      </td>
                                      <td className="px-3 py-2.5">
                                        <StatusBadge value={tc.priority} />
                                      </td>
                                      <td className="px-3 py-2.5">
                                        <div className="flex flex-wrap gap-1">
                                          {tc.module_ids.map((mid) => (
                                            <span
                                              key={mid}
                                              className="rounded bg-app-muted px-2 py-0.5 text-[11px] font-medium text-app-text-secondary"
                                            >
                                              {moduleNameById.get(mid) ?? `Module #${mid}`}
                                            </span>
                                          ))}
                                        </div>
                                      </td>
                                      <td
                                        className="px-4 py-2.5 text-right"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <div className="inline-flex items-center gap-1">
                                          <button
                                            type="button"
                                            onClick={() => {
                                              setEditingTestCase(tc);
                                              setTestCaseModalOpen(true);
                                            }}
                                            aria-label={`Edit test case ${tc.title}`}
                                            className="rounded p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
                                          >
                                            <Edit3 className="h-3.5 w-3.5" />
                                          </button>
                                          <button
                                            type="button"
                                            onClick={() =>
                                              setDeleteTarget({ kind: 'testCase', item: tc })
                                            }
                                            aria-label={`Delete test case ${tc.title}`}
                                            className="rounded p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                          >
                                            <Trash2 className="h-3.5 w-3.5" />
                                          </button>
                                        </div>
                                      </td>
                                    </tr>
                                    {expanded && (
                                      <tr className="bg-app-muted/30">
                                        <td colSpan={6} className="px-6 py-4">
                                          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                            <div>
                                              <p className="text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                                                Test Steps
                                              </p>
                                              <pre className="mt-1 whitespace-pre-wrap rounded border border-app-border bg-app-surface p-3 font-mono text-xs text-app-text">
                                                {tc.steps}
                                              </pre>
                                            </div>
                                            <div>
                                              <p className="text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                                                Expected Result
                                              </p>
                                              <div className="mt-1 rounded border border-app-border bg-app-surface p-3 text-xs leading-relaxed text-app-text">
                                                {tc.expected_result}
                                              </div>
                                            </div>
                                          </div>
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
                    </div>
                  )}

                  {/* TAB 4: DEFECTS */}
                  {activeTab === 'defects' && (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            aria-label="Filter defects by module"
                            value={defectModuleFilter}
                            onChange={(e) => setDefectModuleFilter(e.target.value)}
                            className="input-field w-auto py-1.5 text-xs"
                          >
                            <option value="all">All Modules</option>
                            {modules.map((m) => (
                              <option key={m.id} value={String(m.id)}>
                                {m.name}
                              </option>
                            ))}
                          </select>
                          <select
                            aria-label="Filter defects by severity"
                            value={defectSeverityFilter}
                            onChange={(e) => setDefectSeverityFilter(e.target.value)}
                            className="input-field w-auto py-1.5 text-xs"
                          >
                            <option value="all">All Severities</option>
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                          </select>
                        </div>

                        <button
                          type="button"
                          disabled={modules.length === 0}
                          onClick={() => {
                            setEditingDefect(null);
                            setDefectModalOpen(true);
                          }}
                          className="btn-primary text-xs"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Log Defect
                        </button>
                      </div>

                      {defectsQuery.isLoading ? (
                        <LoadingSkeleton rows={4} message="Loading historical defects..." />
                      ) : filteredDefects.length === 0 ? (
                        <EmptyState
                          title="No Defects Recorded"
                          description="Historical defect records help TestImpact AI detect high-risk regression zones."
                        />
                      ) : (
                        <div className="space-y-3">
                          {filteredDefects.map((defect) => (
                            <div
                              key={defect.id}
                              className="rounded-md border border-app-border bg-app-surface p-4"
                            >
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="space-y-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="font-mono text-xs text-app-text-secondary">
                                      DEF-{defect.id}
                                    </span>
                                    <StatusBadge value={defect.severity} />
                                    <span className="rounded bg-app-muted px-2 py-0.5 text-xs font-medium text-app-text-secondary">
                                      {moduleNameById.get(defect.module_id) ??
                                        `Module #${defect.module_id}`}
                                    </span>
                                  </div>
                                  <h4 className="text-sm font-bold text-app-text">
                                    {defect.title}
                                  </h4>
                                </div>
                                <div className="flex items-center gap-1">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setEditingDefect(defect);
                                      setDefectModalOpen(true);
                                    }}
                                    aria-label={`Edit defect ${defect.title}`}
                                    className="rounded p-1.5 text-app-text-secondary hover:bg-app-muted hover:text-app-text"
                                  >
                                    <Edit3 className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setDeleteTarget({ kind: 'defect', item: defect })
                                    }
                                    aria-label={`Delete defect ${defect.title}`}
                                    className="rounded p-1.5 text-app-text-secondary hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </div>
                              <p className="mt-2 text-xs leading-relaxed text-app-text-secondary">
                                {defect.description}
                              </p>
                              {defect.resolution_notes && (
                                <div className="mt-2.5 rounded border border-app-border bg-app-muted/50 px-3 py-2 text-xs">
                                  <span className="font-semibold text-app-text">
                                    Resolution Notes:{' '}
                                  </span>
                                  <span className="text-app-text-secondary">
                                    {defect.resolution_notes}
                                  </span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 5: TEST EXECUTIONS */}
                  {activeTab === 'executions' && (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            aria-label="Filter executions by test case"
                            value={execTcFilter}
                            onChange={(e) => setExecTcFilter(e.target.value)}
                            className="input-field max-w-[240px] py-1.5 text-xs"
                          >
                            <option value="all">All Test Cases</option>
                            {testCases.map((tc) => (
                              <option key={tc.id} value={String(tc.id)}>
                                TC-{tc.id}: {tc.title}
                              </option>
                            ))}
                          </select>
                          <select
                            aria-label="Filter executions by status"
                            value={execStatusFilter}
                            onChange={(e) => setExecStatusFilter(e.target.value)}
                            className="input-field w-auto py-1.5 text-xs"
                          >
                            <option value="all">All Results</option>
                            <option value="passed">Passed</option>
                            <option value="failed">Failed</option>
                            <option value="blocked">Blocked</option>
                          </select>
                        </div>

                        <button
                          type="button"
                          disabled={testCases.length === 0}
                          onClick={() => setExecModalOpen(true)}
                          className="btn-primary text-xs"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Record Execution
                        </button>
                      </div>

                      {executionsQuery.isLoading ? (
                        <LoadingSkeleton rows={4} message="Loading test execution logs..." />
                      ) : filteredExecutions.length === 0 ? (
                        <EmptyState
                          title="No Execution Records"
                          description="Record pass, fail, or blocked runs for test cases in this project."
                        />
                      ) : (
                        <div className="overflow-x-auto rounded-md border border-app-border">
                          <table className="w-full text-left text-sm">
                            <thead className="border-b border-app-border bg-app-muted/60 text-xs font-semibold uppercase tracking-wide text-app-text-secondary">
                              <tr>
                                <th className="px-4 py-2.5">Exec ID</th>
                                <th className="px-4 py-2.5">Test Case</th>
                                <th className="px-4 py-2.5">Result</th>
                                <th className="px-4 py-2.5">Build Version</th>
                                <th className="px-4 py-2.5">Executed At</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-app-border">
                              {filteredExecutions.map((ex) => (
                                <tr key={ex.id} className="hover:bg-app-muted/30">
                                  <td className="px-4 py-2.5 font-mono text-xs text-app-text-secondary">
                                    EX-{ex.id}
                                  </td>
                                  <td className="px-4 py-2.5 font-medium text-app-text">
                                    <span className="mr-1.5 font-mono text-xs text-app-text-secondary">
                                      TC-{ex.test_case_id}
                                    </span>
                                    {testCaseTitleById.get(ex.test_case_id) ?? 'Unknown Test Case'}
                                  </td>
                                  <td className="px-4 py-2.5">
                                    <StatusBadge value={ex.status} />
                                  </td>
                                  <td className="px-4 py-2.5 font-mono text-xs text-app-text-secondary">
                                    {ex.build_version || '—'}
                                  </td>
                                  <td className="whitespace-nowrap px-4 py-2.5 text-xs text-app-text-secondary">
                                    {formatDateTime(ex.executed_at)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>
      )}

      {/* Modals */}
      <ProjectFormModal
        isOpen={projectModalOpen}
        onClose={() => {
          setProjectModalOpen(false);
          setEditingProject(null);
        }}
        initialProject={editingProject}
        onSubmit={async (values) => {
          await saveProjectMutation.mutateAsync(values);
        }}
        isSubmitting={saveProjectMutation.isPending}
      />

      <ModuleFormModal
        isOpen={moduleModalOpen}
        onClose={() => {
          setModuleModalOpen(false);
          setEditingModule(null);
        }}
        initialModule={editingModule}
        onSubmit={async (values) => {
          await saveModuleMutation.mutateAsync(values);
        }}
        isSubmitting={saveModuleMutation.isPending}
      />

      <TestCaseFormModal
        isOpen={testCaseModalOpen}
        onClose={() => {
          setTestCaseModalOpen(false);
          setEditingTestCase(null);
        }}
        modules={modules}
        initialTestCase={editingTestCase}
        onSubmit={async (values) => {
          await saveTestCaseMutation.mutateAsync(values);
        }}
        isSubmitting={saveTestCaseMutation.isPending}
      />

      <DefectFormModal
        isOpen={defectModalOpen}
        onClose={() => {
          setDefectModalOpen(false);
          setEditingDefect(null);
        }}
        modules={modules}
        initialDefect={editingDefect}
        onSubmit={async (values) => {
          await saveDefectMutation.mutateAsync(values);
        }}
        isSubmitting={saveDefectMutation.isPending}
      />

      <ExecutionFormModal
        isOpen={execModalOpen}
        onClose={() => setExecModalOpen(false)}
        testCases={testCases}
        onSubmit={async (values) => {
          await createExecMutation.mutateAsync(values);
        }}
        isSubmitting={createExecMutation.isPending}
      />

      <ConfirmModal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget);
          }
        }}
        title={deleteConfirmInfo.title}
        message={deleteConfirmInfo.message}
        confirmLabel="Delete"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />
    </div>
  );
};

