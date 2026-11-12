import React from 'react';
import { formatStatusLabel } from '../../utils/formatters';

type BadgeTone = 'red' | 'amber' | 'teal' | 'green' | 'indigo' | 'slate';

const TONE_CLASSES: Record<BadgeTone, string> = {
  red: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900/60',
  amber:
    'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/60',
  teal: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-900/60',
  green:
    'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/60',
  indigo:
    'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-900/60',
  slate:
    'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
};

export function resolveStatusTone(value: string): BadgeTone {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'high' || normalized === 'critical' || normalized === 'failed' || normalized === 'rejected') {
    return 'red';
  }
  if (normalized === 'medium' || normalized === 'blocked' || normalized === 'pending' || normalized === 'in_progress') {
    return 'amber';
  }
  if (normalized === 'low') {
    return 'teal';
  }
  if (normalized === 'completed' || normalized === 'passed' || normalized === 'accepted') {
    return 'green';
  }
  if (normalized === 'running' || normalized === 'submitted') {
    return 'indigo';
  }
  return 'slate';
}

interface StatusBadgeProps {
  value: string;
  tone?: BadgeTone;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  value,
  tone,
  className = '',
}) => {
  const resolvedTone = tone ?? resolveStatusTone(value);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[resolvedTone]} ${className}`}
    >
      {formatStatusLabel(value)}
    </span>
  );
};

