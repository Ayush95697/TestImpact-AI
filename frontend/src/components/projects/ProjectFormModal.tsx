import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Modal } from '../common/Modal';
import type { Project } from '../../types/api';

const projectSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, 'Project name must be at least 2 characters')
    .max(120, 'Project name must be 120 characters or fewer'),
  description: z.string().optional(),
});

type ProjectFormValues = z.infer<typeof projectSchema>;

interface ProjectFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: { name: string; description: string | null }) => Promise<void>;
  initialProject?: Project | null;
  isSubmitting?: boolean;
}

export const ProjectFormModal: React.FC<ProjectFormModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialProject,
  isSubmitting = false,
}) => {
  const isEditing = Boolean(initialProject);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: initialProject?.name ?? '',
      description: initialProject?.description ?? '',
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        name: initialProject?.name ?? '',
        description: initialProject?.description ?? '',
      });
    }
  }, [isOpen, initialProject, reset]);

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
      title={isEditing ? 'Edit Project' : 'Create Project'}
      subtitle={
        isEditing
          ? 'Update the project name or scope description.'
          : 'Register a new software system for regression impact tracking.'
      }
      size="md"
    >
      <form onSubmit={handleFormSubmit} className="space-y-4">
        <div>
          <label htmlFor="project-name" className="field-label">
            Project Name <span className="text-red-500">*</span>
          </label>
          <input
            id="project-name"
            type="text"
            placeholder="e.g., Core Banking Platform"
            className="input-field"
            {...register('name')}
          />
          {errors.name && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="project-description" className="field-label">
            Description
          </label>
          <textarea
            id="project-description"
            rows={3}
            placeholder="Describe the application domain, services, or QA scope..."
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
            {isEditing ? 'Save Changes' : 'Create Project'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

