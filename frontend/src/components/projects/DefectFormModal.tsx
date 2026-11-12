import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Modal } from '../common/Modal';
import type { Defect, ModuleItem } from '../../types/api';

const defectSchema = z.object({
  title: z.string().trim().min(1, 'Defect title is required'),
  module_id: z.coerce.number().int().positive('Select a module'),
  severity: z.string().trim().min(1, 'Severity is required'),
  description: z.string().trim().min(1, 'Description is required'),
  resolution_notes: z.string().optional(),
});

type DefectFormValues = z.infer<typeof defectSchema>;

interface DefectFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  modules: ModuleItem[];
  onSubmit: (values: {
    title: string;
    module_id: number;
    severity: string;
    description: string;
    resolution_notes: string | null;
  }) => Promise<void>;
  initialDefect?: Defect | null;
  isSubmitting?: boolean;
}

const SEVERITY_OPTIONS = ['Critical', 'High', 'Medium', 'Low'];

export const DefectFormModal: React.FC<DefectFormModalProps> = ({
  isOpen,
  onClose,
  modules,
  onSubmit,
  initialDefect,
  isSubmitting = false,
}) => {
  const isEditing = Boolean(initialDefect);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DefectFormValues>({
    resolver: zodResolver(defectSchema),
    defaultValues: {
      title: initialDefect?.title ?? '',
      module_id: initialDefect?.module_id ?? modules[0]?.id ?? 0,
      severity: initialDefect?.severity ?? 'High',
      description: initialDefect?.description ?? '',
      resolution_notes: initialDefect?.resolution_notes ?? '',
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        title: initialDefect?.title ?? '',
        module_id: initialDefect?.module_id ?? modules[0]?.id ?? 0,
        severity: initialDefect?.severity ?? 'High',
        description: initialDefect?.description ?? '',
        resolution_notes: initialDefect?.resolution_notes ?? '',
      });
    }
  }, [isOpen, initialDefect, modules, reset]);

  const handleFormSubmit = handleSubmit(async (data) => {
    const trimmedNotes = data.resolution_notes?.trim() ?? '';
    await onSubmit({
      title: data.title.trim(),
      module_id: data.module_id,
      severity: data.severity.trim(),
      description: data.description.trim(),
      resolution_notes: trimmedNotes ? trimmedNotes : null,
    });
  });

  return (
    <Modal
      isOpen={isOpen}
      onClose={isSubmitting ? () => undefined : onClose}
      title={isEditing ? 'Edit Defect' : 'Log Historical Defect'}
      subtitle="Historical defect records enrich vector search and impact scoring."
      size="lg"
    >
      <form onSubmit={handleFormSubmit} className="space-y-4">
        <div>
          <label htmlFor="defect-title" className="field-label">
            Defect Title <span className="text-red-500">*</span>
          </label>
          <input
            id="defect-title"
            type="text"
            placeholder="e.g., Session token expires prematurely under load"
            className="input-field"
            {...register('title')}
          />
          {errors.title && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.title.message}</p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="defect-module" className="field-label">
              Module <span className="text-red-500">*</span>
            </label>
            <select
              id="defect-module"
              className="input-field"
              disabled={isEditing}
              {...register('module_id')}
            >
              {modules.length === 0 && <option value={0}>No modules available</option>}
              {modules.map((mod) => (
                <option key={mod.id} value={mod.id}>
                  {mod.name}
                </option>
              ))}
            </select>
            {errors.module_id && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                {errors.module_id.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="defect-severity" className="field-label">
              Severity <span className="text-red-500">*</span>
            </label>
            <select id="defect-severity" className="input-field" {...register('severity')}>
              {SEVERITY_OPTIONS.map((sev) => (
                <option key={sev} value={sev}>
                  {sev}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="defect-description" className="field-label">
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="defect-description"
            rows={3}
            placeholder="Describe root cause, failure symptoms, and affected flow..."
            className="input-field resize-y"
            {...register('description')}
          />
          {errors.description && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.description.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="defect-notes" className="field-label">
            Resolution Notes
          </label>
          <textarea
            id="defect-notes"
            rows={2}
            placeholder="Optional remediation notes or fix summary..."
            className="input-field resize-y"
            {...register('resolution_notes')}
          />
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-app-border pt-4">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || modules.length === 0}
            className="btn-primary"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEditing ? 'Save Changes' : 'Create Defect'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

