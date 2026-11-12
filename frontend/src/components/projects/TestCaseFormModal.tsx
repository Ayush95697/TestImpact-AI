import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Modal } from '../common/Modal';
import type { ModuleItem, TestCase } from '../../types/api';

const testCaseSchema = z.object({
  title: z.string().trim().min(1, 'Title is required'),
  priority: z.string().trim().min(1, 'Priority is required'),
  steps: z.string().trim().min(1, 'Execution steps are required'),
  expected_result: z.string().trim().min(1, 'Expected result is required'),
  module_ids: z.array(z.number()).min(1, 'Select at least one associated module'),
});

type TestCaseFormValues = z.infer<typeof testCaseSchema>;

interface TestCaseFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  modules: ModuleItem[];
  onSubmit: (values: TestCaseFormValues) => Promise<void>;
  initialTestCase?: TestCase | null;
  isSubmitting?: boolean;
}

const PRIORITY_OPTIONS = ['Critical', 'High', 'Medium', 'Low'];

export const TestCaseFormModal: React.FC<TestCaseFormModalProps> = ({
  isOpen,
  onClose,
  modules,
  onSubmit,
  initialTestCase,
  isSubmitting = false,
}) => {
  const isEditing = Boolean(initialTestCase);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<TestCaseFormValues>({
    resolver: zodResolver(testCaseSchema),
    defaultValues: {
      title: initialTestCase?.title ?? '',
      priority: initialTestCase?.priority ?? 'High',
      steps: initialTestCase?.steps ?? '',
      expected_result: initialTestCase?.expected_result ?? '',
      module_ids: initialTestCase?.module_ids ?? [],
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        title: initialTestCase?.title ?? '',
        priority: initialTestCase?.priority ?? 'High',
        steps: initialTestCase?.steps ?? '',
        expected_result: initialTestCase?.expected_result ?? '',
        module_ids: initialTestCase?.module_ids ?? [],
      });
    }
  }, [isOpen, initialTestCase, reset]);

  const selectedModuleIds = watch('module_ids') ?? [];

  const toggleModule = (moduleId: number) => {
    const exists = selectedModuleIds.includes(moduleId);
    const next = exists
      ? selectedModuleIds.filter((id) => id !== moduleId)
      : [...selectedModuleIds, moduleId];
    setValue('module_ids', next, { shouldValidate: true });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={isSubmitting ? () => undefined : onClose}
      title={isEditing ? 'Edit Test Case' : 'Create Test Case'}
      subtitle="Specify verification steps, expected outcome, priority, and covered modules."
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label htmlFor="tc-title" className="field-label">
              Test Case Title <span className="text-red-500">*</span>
            </label>
            <input
              id="tc-title"
              type="text"
              placeholder="e.g., Verify valid MFA login blocks expired tokens"
              className="input-field"
              {...register('title')}
            />
            {errors.title && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.title.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="tc-priority" className="field-label">
              Priority <span className="text-red-500">*</span>
            </label>
            <select id="tc-priority" className="input-field" {...register('priority')}>
              {PRIORITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            {errors.priority && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                {errors.priority.message}
              </p>
            )}
          </div>
        </div>

        <div>
          <span className="field-label">
            Associated Modules <span className="text-red-500">*</span>
          </span>
          {modules.length === 0 ? (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
              Create at least one module in this project before adding test cases.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 rounded-md border border-app-border p-3 sm:grid-cols-2">
              {modules.map((mod) => {
                const checked = selectedModuleIds.includes(mod.id);
                return (
                  <label
                    key={mod.id}
                    className={`flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-xs transition-colors ${
                      checked
                        ? 'border-indigo-500 bg-indigo-50/70 text-app-text dark:bg-indigo-950/30'
                        : 'border-app-border hover:bg-app-muted/60'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleModule(mod.id)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-medium">{mod.name}</span>
                  </label>
                );
              })}
            </div>
          )}
          {errors.module_ids && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.module_ids.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="tc-steps" className="field-label">
            Execution Steps <span className="text-red-500">*</span>
          </label>
          <textarea
            id="tc-steps"
            rows={4}
            placeholder={'1. Open login endpoint\n2. Submit expired session token\n3. Inspect response'}
            className="input-field resize-y font-mono text-xs"
            {...register('steps')}
          />
          {errors.steps && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.steps.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="tc-expected" className="field-label">
            Expected Result <span className="text-red-500">*</span>
          </label>
          <textarea
            id="tc-expected"
            rows={2}
            placeholder="User receives HTTP 401 and transfer action is aborted."
            className="input-field resize-y"
            {...register('expected_result')}
          />
          {errors.expected_result && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.expected_result.message}
            </p>
          )}
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
            {isEditing ? 'Save Changes' : 'Create Test Case'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

