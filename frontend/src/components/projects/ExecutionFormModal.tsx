import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Modal } from '../common/Modal';
import type { ExecutionStatus, TestCase } from '../../types/api';

const executionSchema = z.object({
  test_case_id: z.coerce.number().int().positive('Select a test case'),
  status: z.enum(['passed', 'failed', 'blocked']),
  build_version: z.string().optional(),
});

type ExecutionFormValues = z.infer<typeof executionSchema>;

interface ExecutionFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  testCases: TestCase[];
  onSubmit: (values: {
    test_case_id: number;
    status: ExecutionStatus;
    build_version: string | null;
  }) => Promise<void>;
  isSubmitting?: boolean;
}

export const ExecutionFormModal: React.FC<ExecutionFormModalProps> = ({
  isOpen,
  onClose,
  testCases,
  onSubmit,
  isSubmitting = false,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ExecutionFormValues>({
    resolver: zodResolver(executionSchema),
    defaultValues: {
      test_case_id: testCases[0]?.id ?? 0,
      status: 'passed',
      build_version: '',
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        test_case_id: testCases[0]?.id ?? 0,
        status: 'passed',
        build_version: '',
      });
    }
  }, [isOpen, testCases, reset]);

  const handleFormSubmit = handleSubmit(async (data) => {
    const trimmedBuild = data.build_version?.trim() ?? '';
    await onSubmit({
      test_case_id: data.test_case_id,
      status: data.status,
      build_version: trimmedBuild ? trimmedBuild : null,
    });
  });

  return (
    <Modal
      isOpen={isOpen}
      onClose={isSubmitting ? () => undefined : onClose}
      title="Record Test Execution"
      subtitle="Log a test run result to track execution history for impact analysis."
      size="md"
    >
      <form onSubmit={handleFormSubmit} className="space-y-4">
        <div>
          <label htmlFor="exec-tc" className="field-label">
            Test Case <span className="text-red-500">*</span>
          </label>
          <select id="exec-tc" className="input-field" {...register('test_case_id')}>
            {testCases.length === 0 && <option value={0}>No test cases available</option>}
            {testCases.map((tc) => (
              <option key={tc.id} value={tc.id}>
                TC-{tc.id}: {tc.title}
              </option>
            ))}
          </select>
          {errors.test_case_id && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.test_case_id.message}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="exec-status" className="field-label">
              Execution Result <span className="text-red-500">*</span>
            </label>
            <select id="exec-status" className="input-field" {...register('status')}>
              <option value="passed">Passed</option>
              <option value="failed">Failed</option>
              <option value="blocked">Blocked</option>
            </select>
          </div>

          <div>
            <label htmlFor="exec-build" className="field-label">
              Build Version
            </label>
            <input
              id="exec-build"
              type="text"
              placeholder="e.g., v2.4.1"
              className="input-field font-mono"
              {...register('build_version')}
            />
          </div>
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
            disabled={isSubmitting || testCases.length === 0}
            className="btn-primary"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Record Execution
          </button>
        </div>
      </form>
    </Modal>
  );
};

