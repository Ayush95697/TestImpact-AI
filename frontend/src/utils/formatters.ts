export function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

export function formatShortDate(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  }).format(parsed);
}

export function formatScore(score: number): string {
  return Number.isFinite(score) ? score.toFixed(1) : '0.0';
}

export function formatStatusLabel(status?: string | null): string {
  if (!status) return 'Unknown';
  return status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export const SCORE_BREAKDOWN_LABELS: Record<string, { label: string; max: number }> = {
  direct_module_match: { label: 'Direct Module Match', max: 40 },
  semantic_search_match: { label: 'Semantic Similarity Search', max: 25 },
  related_defect_match: { label: 'Related Defect History', max: 20 },
  related_execution_match: { label: 'Historical Execution Signal', max: 15 },
};

