import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Info,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { formatDateTime } from '../../utils/formatters';
import type { AnalysisExplanation, Recommendation } from '../../types/api';

interface AIExplanationPanelProps {
  explanation: AnalysisExplanation | null;
  recommendations: Recommendation[];
  isLoadingInitial: boolean;
  isGenerating: boolean;
  generationError: string | null;
  llmAvailable: boolean;
  canGenerate: boolean;
  onGenerate: () => void;
}

export const AIExplanationPanel: React.FC<AIExplanationPanelProps> = ({
  explanation,
  recommendations,
  isLoadingInitial,
  isGenerating,
  generationError,
  llmAvailable,
  canGenerate,
  onGenerate,
}) => {
  const recLookup = new Map<number, Recommendation>();
  for (const r of recommendations) {
    recLookup.set(r.id, r);
  }

  // When LLM is unavailable and there is no persisted explanation, show only a subtle disabled status bar
  if (!llmAvailable && !explanation && !isLoadingInitial) {
    return (
      <div className="surface-card flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 text-xs text-app-text-secondary">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-app-text-secondary" />
          <span>
            <strong className="font-semibold text-app-text">AI Explanation Unavailable:</strong>{' '}
            Company LLaMA explanation service is currently unconfigured. Deterministic scoring and QA review remain fully operational.
          </span>
        </div>
        <span className="rounded-full border border-app-border bg-app-muted px-2.5 py-0.5 font-mono text-[11px]">
          LLM Disabled
        </span>
      </div>
    );
  }

  return (
    <section
      aria-label="AI Explanation Advisory Panel"
      className="rounded-lg border border-indigo-200 bg-indigo-50/40 shadow-subtle dark:border-indigo-800/60 dark:bg-indigo-950/20"
    >
      {/* Distinct Advisory Header */}
      <div className="flex flex-col gap-3 border-b border-indigo-200/80 px-5 py-4 dark:border-indigo-800/50 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-indigo-600 text-white">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-heading text-sm font-bold text-app-text">
                AI-Assisted Advisory Explanation
              </h3>
              <span className="rounded border border-indigo-300 bg-indigo-100/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-800 dark:border-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-200">
                Advisory Only
              </span>
              {explanation && (
                <span className="rounded bg-app-surface px-2 py-0.5 font-mono text-[11px] text-app-text-secondary border border-app-border">
                  {explanation.model_name}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-app-text-secondary">
              Explains deterministic evidence and recommendations without altering test IDs, heuristic scores, ranks, or QA review decisions.
            </p>
          </div>
        </div>

        {llmAvailable && canGenerate && (
          <button
            type="button"
            disabled={isGenerating}
            onClick={onGenerate}
            className="btn-primary shrink-0 text-xs"
          >
            {isGenerating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : explanation ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {isGenerating
              ? 'Generating Explanation...'
              : explanation
              ? 'Regenerate AI Explanation'
              : 'Generate AI Explanation'}
          </button>
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Error state scoped locally so deterministic table remains completely usable */}
        {generationError && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">AI explanation request failed</p>
              <p className="mt-0.5">{generationError}</p>
            </div>
          </div>
        )}

        {/* Scoped non-blocking generating notice */}
        {isGenerating && (
          <div className="flex items-center gap-2.5 rounded-md border border-indigo-200 bg-app-surface px-4 py-3 text-xs text-app-text-secondary dark:border-indigo-800/50">
            <Loader2 className="h-4 w-4 animate-spin text-indigo-600 dark:text-indigo-400" />
            <span>
              Generating evidence-grounded summary with LLaMA 3.1 8B. You may continue inspecting and reviewing deterministic recommendations below.
            </span>
          </div>
        )}

        {isLoadingInitial && !explanation && !isGenerating && (
          <div className="flex items-center gap-2 text-xs text-app-text-secondary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Checking for saved AI explanation...</span>
          </div>
        )}

        {!isLoadingInitial && !explanation && !isGenerating && llmAvailable && (
          <div className="rounded-md border border-dashed border-indigo-300/80 bg-app-surface/70 px-4 py-4 text-xs text-app-text-secondary dark:border-indigo-800/60">
            {canGenerate
              ? 'No AI explanation has been generated for this run yet. Click "Generate AI Explanation" above to synthesize a grounded narrative from persisted evidence.'
              : 'AI explanations are available only for completed analysis runs with recommendations.'}
          </div>
        )}

        {explanation && (
          <div className="space-y-4">
            {/* Overall Summary */}
            <div className="rounded-md border border-app-border bg-app-surface p-4">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <h4 className="text-xs font-bold uppercase tracking-wide text-app-text-secondary">
                  Overall Summary
                </h4>
                <span className="text-[11px] text-app-text-secondary">
                  Generated {formatDateTime(explanation.created_at)}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-app-text">
                {explanation.overall_summary}
              </p>
            </div>

            {/* Risk Observations & Limitations */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-md border border-app-border bg-app-surface p-4">
                <h4 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Risk Observations
                </h4>
                {explanation.risk_observations.length === 0 ? (
                  <p className="text-xs text-app-text-secondary">No specific risk observations noted.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs leading-relaxed text-app-text">
                    {explanation.risk_observations.map((obs, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                        <span>{obs}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="rounded-md border border-app-border bg-app-surface p-4">
                <h4 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
                  <Info className="h-3.5 w-3.5" />
                  Limitations &amp; Scope Notes
                </h4>
                {explanation.limitations.length === 0 ? (
                  <p className="text-xs text-app-text-secondary">No additional limitations listed.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs leading-relaxed text-app-text-secondary">
                    {explanation.limitations.map((lim, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                        <span>{lim}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Per-Test Explanations */}
            {explanation.recommendations.length > 0 && (
              <div className="rounded-md border border-app-border bg-app-surface p-4">
                <h4 className="mb-3 text-xs font-bold uppercase tracking-wide text-app-text-secondary">
                  Per-Test AI Explanations &amp; Evidence References
                </h4>
                <div className="space-y-3">
                  {explanation.recommendations.map((item) => {
                    const matchedRec = recLookup.get(item.recommendation_id);
                    return (
                      <div
                        key={item.recommendation_id}
                        className="rounded-md border border-app-border bg-app-muted/40 p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            {matchedRec && (
                              <span className="rounded bg-indigo-600 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">
                                #{matchedRec.rank}
                              </span>
                            )}
                            <span className="font-mono text-xs font-semibold text-app-text-secondary">
                              TC-{item.test_case_id}
                            </span>
                            <span className="text-xs font-bold text-app-text">
                              {matchedRec?.test_case_title ?? `Recommendation #${item.recommendation_id}`}
                            </span>
                          </div>
                          {item.evidence_refs.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1">
                              {item.evidence_refs.map((ref, refIdx) => (
                                <span
                                  key={`${ref.source_type}-${ref.source_id}-${refIdx}`}
                                  className="rounded border border-app-border-strong bg-app-surface px-2 py-0.5 font-mono text-[10px] font-medium text-teal-700 dark:text-teal-300"
                                >
                                  {ref.source_type} #{ref.source_id}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-app-text">
                          {item.explanation}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

