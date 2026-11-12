import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Modal } from '../common/Modal';
import type { ModuleItem } from '../../types/api';

const moduleSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, 'Module name must be at least 2 characters')
    .max(120, 'Module name must be 120 characters or fewer'),
  description: z.string().optional(),
});

type ModuleFormValues = z.infer<typeof moduleSchema>;

interface ModuleFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: { name: string; description: string | null }) => Promise<void>;
  initialModule?: ModuleItem | null;
  isSubmitting?: boolean;
}

export const ModuleFormModal: React.FC<ModuleFormModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialModule,
  isSubmitting = false,
}) => {
  const isEditing = Boolean(initialModule);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ModuleFormValues>({
    resolver: zodResolver(moduleSchema),
    defaultValues: {
      name: initialModule?.name ?? '',
      description: initialModule?.description ?? '',
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        name: initialModule?.name ?? '',
        description: initialModule?.description ?? '',
      });
    }
  }, [isOpen, initialModule, reset]);

  const handleFormSubmit = handleSubmit(async (data) => {
    const trimmedDesc = data.description?.trim() ?? '';
    await onSubmit({
      name: data.name.trim(),
      description: trimmedDesc ? trimmedDesc : null,
    });
  });

  return (
    <Modal
      isOpen={isOpen}
      onClose={isSubmitting ? () => undefined : onClose}
      title={isEditing ? 'Edit Module' : 'Create Module'}
      subtitle="Define an architectural component or feature domain inside the project."
      size="md"
    >
      <form onSubmit={handleFormSubmit} className="space-y-4">
        <div>
          <label htmlFor="module-name" className="field-label">
            Module Name <span className="text-red-500">*</span>
          </label>
          <input
            id="module-name"
            type="text"
            placeholder="e.g., Authentication"
            className="input-field"
            {...register('name')}
          />
          {errors.name && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="module-description" className="field-label">
            Description
          </label>
          <textarea
            id="module-description"
            rows={3}
            placeholder="Summarize module responsibilities and API boundaries..."
            className="input-field resize-y"
            {...register('description')}
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
          <button type="submit" disabled={isSubmitting} className="btn-primary">
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEditing ? 'Save Changes' : 'Create Module'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

