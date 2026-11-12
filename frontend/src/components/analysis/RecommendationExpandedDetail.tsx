import React, { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Bug, ClipboardCheck, History, Layers, Loader2 } from 'lucide-react';
import { testCaseService } from '../../services/testCaseService';
import { testExecutionService } from '../../services/testExecutionService';
import { defectService } from '../../services/defectService';
import { moduleService } from '../../services/moduleService';
import { formatDateTime, SCORE_BREAKDOWN_LABELS } from '../../utils/formatters';
import { StatusBadge } from '../common/StatusBadge';
import type { Defect, Recommendation, TestExecution } from '../../types/api';

interface RecommendationExpandedDetailProps {
  recommendation: Recommendation;
  projectId: number | null;
}

export const RecommendationExpandedDetail: React.FC<RecommendationExpandedDetailProps> = ({
  recommendation,
  projectId,
}) => {
  const tcQuery = useQuery({
    queryKey: ['test-cases', 'detail', recommendation.test_case_id],
    queryFn: () => testCaseService.getTestCase(recommendation.test_case_id),
    staleTime: 60000,
  });

  const executionsQuery = useQuery({
    queryKey: ['test-executions', { test_case_id: recommendation.test_case_id }],
    queryFn: () =>
      testExecutionService.listExecutions({ test_case_id: recommendation.test_case_id }),
    staleTime: 60000,
  });

  const effectiveProjectId = projectId ?? tcQuery.data?.project_id ?? null;

  const modulesQuery = useQuery({
    queryKey: ['projects', effectiveProjectId, 'modules'],
    queryFn: () => moduleService.listByProject(effectiveProjectId!),
    enabled: effectiveProjectId !== null,
    staleTime: 60000,
  });

  const citedDefectIds = useMemo(
    () =>
      Array.from(
        new Set(
          recommendation.supporting_evidence
            .filter((ev) => ev.source_type === 'defect' && ev.source_id > 0)
            .map((ev) => ev.source_id)
        )
      ),
    [recommendation.supporting_evidence]
  );

  const defectDetailQueries = useQueries({
    queries: citedDefectIds.map((id) => ({
      queryKey: ['defects', 'detail', id],
      queryFn: () => defectService.getDefect(id),
      staleTime: 60000,
    })),
  });

  const moduleDefectsQuery = useQuery({
    queryKey: ['defects', { project_id: effectiveProjectId }],
    queryFn: () => defectService.listDefects({ project_id: effectiveProjectId! }),
    enabled: effectiveProjectId !== null,
    staleTime: 60000,
  });

  const moduleNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const m of modulesQuery.data ?? []) map.set(m.id, m.name);
    return map;
  }, [modulesQuery.data]);

  const relatedDefects = useMemo(() => {
    const byId = new Map<number, Defect>();
    for (const q of defectDetailQueries) {
      if (q.data) byId.set(q.data.id, q.data);
    }
    const tcModuleIds = new Set(tcQuery.data?.module_ids ?? []);
    for (const d of moduleDefectsQuery.data ?? []) {
      if (tcModuleIds.has(d.module_id)) {
        byId.set(d.id, d);
      }
    }
    return Array.from(byId.values());
  }, [defectDetailQueries, moduleDefectsQuery.data, tcQuery.data?.module_ids]);

  const executions: TestExecution[] = useMemo(() => {
    const list = executionsQuery.data ?? [];
    return [...list].sort((a, b) => b.id - a.id);
  }, [executionsQuery.data]);

  const breakdownEntries = Object.entries(recommendation.score_breakdown || {});

  return (
    <div className="space-y-4 bg-app-muted/35 p-5">
      {/* Row 1: Deterministic Explanation + Score Breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-md border border-app-border bg-app-surface p-4 lg:col-span-7">
          <h4 className="text-xs font-bold uppercase tracking-wide text-app-text-secondary">
            Deterministic Rationale
          </h4>
          <p className="mt-2 text-sm leading-relaxed text-app-text">
            {recommendation.reason}
          </p>
        </div>

        <div className="rounded-md border border-app-border bg-app-surface p-4 lg:col-span-5">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wide text-app-text-secondary">
              Heuristic Score Breakdown
            </h4>
            <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
              {recommendation.score.toFixed(1)} / 100 pts
            </span>
          </div>
          <div className="mt-3 space-y-2.5">
            {breakdownEntries.map(([key, value]) => {
              const meta = SCORE_BREAKDOWN_LABELS[key] ?? { label: key, max: 40 };
              const numericVal = typeof value === 'number' ? value : Number(value) || 0;
              const widthRatio = Math.min(100, Math.max(0, (numericVal / meta.max) * 100));
              return (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-app-text">{meta.label}</span>
                    <span className="font-mono font-semibold text-app-text">
                      +{numericVal.toFixed(1)} <span className="text-app-text-secondary">/ {meta.max}</span>
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-app-muted">
                    <div
                      className={`h-full rounded-full ${
                        numericVal > 0 ? 'bg-indigo-600 dark:bg-indigo-500' : 'bg-transparent'
                      }`}
                      style={{ width: `${widthRatio}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Row 2: Test Case Details + Modules */}
      <div className="rounded-md border border-app-border bg-app-surface p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
            <ClipboardCheck className="h-3.5 w-3.5" />
            Test Case Specification (TC-{recommendation.test_case_id})
          </h4>
          {tcQuery.data && (
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge value={tcQuery.data.priority} />
              {tcQuery.data.module_ids.map((mid) => (
                <span
                  key={mid}
                  className="inline-flex items-center gap-1 rounded bg-app-muted px-2 py-0.5 text-[11px] font-medium text-app-text-secondary"
                >
                  <Layers className="h-3 w-3" />
                  {moduleNameById.get(mid) ?? `Module #${mid}`}
                </span>
              ))}
            </div>
          )}
        </div>

        {tcQuery.isLoading ? (
          <div className="flex items-center gap-2 text-xs text-app-text-secondary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading test steps and expected result...
          </div>
        ) : tcQuery.data ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Execution Steps
              </p>
              <pre className="mt-1 whitespace-pre-wrap rounded border border-app-border bg-app-muted/40 p-3 font-mono text-xs text-app-text">
                {tcQuery.data.steps}
              </pre>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-app-text-secondary">
                Expected Result
              </p>
              <div className="mt-1 rounded border border-app-border bg-app-muted/40 p-3 text-xs leading-relaxed text-app-text">
                {tcQuery.data.expected_result}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-app-text-secondary">
            Unable to load full test case details.
          </p>
        )}
      </div>

      {/* Row 3: Supporting Evidence, Related Defects, Historical Executions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Supporting Evidence */}
        <div className="rounded-md border border-app-border bg-app-surface p-4">
          <h4 className="mb-2.5 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
            Supporting Evidence ({recommendation.supporting_evidence.length})
          </h4>
          {recommendation.supporting_evidence.length === 0 ? (
            <p className="text-xs text-app-text-secondary">No supporting evidence records cited.</p>
          ) : (
            <div className="space-y-2">
              {recommendation.supporting_evidence.map((ev, idx) => (
                <div
                  key={`${ev.source_type}-${ev.source_id}-${idx}`}
                  className="rounded border border-app-border bg-app-muted/35 p-2.5 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="rounded bg-indigo-50 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                      {ev.source_type} #{ev.source_id}
                    </span>
                    <div className="flex items-center gap-2 font-mono text-[10px] text-app-text-secondary">
                      {ev.retrieval_rank != null && <span>rank #{ev.retrieval_rank}</span>}
                      {ev.distance != null && <span>dist {ev.distance.toFixed(3)}</span>}
                    </div>
                  </div>
                  <p className="mt-1 font-medium text-app-text">{ev.title}</p>
                  {ev.module_name && (
                    <p className="mt-0.5 text-[11px] text-app-text-secondary">
                      Module: {ev.module_name}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Related Defects */}
        <div className="rounded-md border border-app-border bg-app-surface p-4">
          <h4 className="mb-2.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
            <Bug className="h-3.5 w-3.5" />
            Related Defect Records ({relatedDefects.length})
          </h4>
          {relatedDefects.length === 0 ? (
            <p className="text-xs text-app-text-secondary">
              No historical defects recorded for this test case&apos;s modules.
            </p>
          ) : (
            <div className="space-y-2">
              {relatedDefects.map((defect) => (
                <div
                  key={defect.id}
                  className="rounded border border-app-border bg-app-muted/35 p-2.5 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] font-semibold text-app-text-secondary">
                      DEF-{defect.id}
                    </span>
                    <StatusBadge value={defect.severity} />
                  </div>
                  <p className="mt-1 font-semibold text-app-text">{defect.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-[11px] text-app-text-secondary">
                    {defect.description}
                  </p>
                  {defect.resolution_notes && (
                    <p className="mt-1 text-[11px] text-teal-700 dark:text-teal-300">
                      Fix: {defect.resolution_notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Historical Executions */}
        <div className="rounded-md border border-app-border bg-app-surface p-4">
          <h4 className="mb-2.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
            <History className="h-3.5 w-3.5" />
            Historical Executions ({executions.length})
          </h4>
          {executionsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-xs text-app-text-secondary">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading execution history...
            </div>
          ) : executions.length === 0 ? (
            <p className="text-xs text-app-text-secondary">
              No historical execution records logged for this test case.
            </p>
          ) : (
            <div className="space-y-2">
              {executions.slice(0, 6).map((ex) => (
                <div
                  key={ex.id}
                  className="flex items-center justify-between gap-2 rounded border border-app-border bg-app-muted/35 p-2.5 text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-app-text-secondary">
                        EX-{ex.id}
                      </span>
                      <StatusBadge value={ex.status} />
                    </div>
                    <p className="mt-1 text-[11px] text-app-text-secondary">
                      {formatDateTime(ex.executed_at)}
                    </p>
                  </div>
                  <span className="font-mono text-[11px] font-medium text-app-text">
                    {ex.build_version || '—'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

