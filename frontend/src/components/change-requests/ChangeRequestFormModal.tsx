import React, { useEffect } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { moduleService } from '../../services/moduleService';
import { Modal } from '../common/Modal';
import type { ChangeRequest, Project } from '../../types/api';

const changeRequestSchema = z.object({
  project_id: z.coerce.number().int().positive('Please select a project'),
  title: z.string().trim().min(1, 'Change title is required'),
  description: z.string().trim().min(1, 'Change description is required'),
  status: z.string().trim().min(1, 'Status is required'),
  module_ids: z.array(z.number()).min(1, 'Select at least one affected module'),
});

type ChangeRequestFormValues = z.infer<typeof changeRequestSchema>;

interface ChangeRequestFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  defaultProjectId?: number | null;
  initialChangeRequest?: ChangeRequest | null;
  onSubmit: (values: ChangeRequestFormValues) => Promise<void>;
  isSubmitting?: boolean;
}

const CR_STATUS_OPTIONS = [
  { value: 'submitted', label: 'Submitted' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

export const ChangeRequestFormModal: React.FC<ChangeRequestFormModalProps> = ({
  isOpen,
  onClose,
  projects,
  defaultProjectId,
  initialChangeRequest,
  onSubmit,
  isSubmitting = false,
}) => {
  const isEditing = Boolean(initialChangeRequest);

  const initialProjId =
    initialChangeRequest?.project_id ?? defaultProjectId ?? projects[0]?.id ?? 0;

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<ChangeRequestFormValues>({
    resolver: zodResolver(changeRequestSchema),
    defaultValues: {
      project_id: initialProjId,
      title: initialChangeRequest?.title ?? '',
      description: initialChangeRequest?.description ?? '',
      status: initialChangeRequest?.status ?? 'submitted',
      module_ids: initialChangeRequest?.module_ids ?? [],
    },
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        project_id:
          initialChangeRequest?.project_id ?? defaultProjectId ?? projects[0]?.id ?? 0,
        title: initialChangeRequest?.title ?? '',
        description: initialChangeRequest?.description ?? '',
        status: initialChangeRequest?.status ?? 'submitted',
        module_ids: initialChangeRequest?.module_ids ?? [],
      });
    }
  }, [isOpen, initialChangeRequest, defaultProjectId, projects, reset]);

  const watchedProjectId = Number(watch('project_id'));
  const selectedModuleIds = watch('module_ids') ?? [];

  const modulesQuery = useQuery({
    queryKey: ['projects', watchedProjectId, 'modules'],
    queryFn: () => moduleService.listByProject(watchedProjectId),
    enabled: isOpen && Number.isFinite(watchedProjectId) && watchedProjectId > 0,
  });

  const projectModules = modulesQuery.data ?? [];

  const handleProjectChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const nextProjectId = Number(event.target.value);
    setValue('project_id', nextProjectId, { shouldValidate: true });
    // Clear selected modules whenever switching project so invalid cross-project IDs cannot persist
    setValue('module_ids', [], { shouldValidate: false });
  };

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
      title={isEditing ? 'Edit Change Request' : 'Create Change Request'}
      subtitle="Describe proposed software changes and affected architectural modules."
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="cr-project" className="field-label">
              Project <span className="text-red-500">*</span>
            </label>
            <select
              id="cr-project"
              disabled={isEditing}
              className="input-field"
              value={watchedProjectId}
              onChange={handleProjectChange}
            >
              {projects.length === 0 && <option value={0}>No projects available</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {errors.project_id && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                {errors.project_id.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="cr-status" className="field-label">
              Workflow Status <span className="text-red-500">*</span>
            </label>
            <select id="cr-status" className="input-field" {...register('status')}>
              {CR_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="cr-title" className="field-label">
            Change Title <span className="text-red-500">*</span>
          </label>
          <input
            id="cr-title"
            type="text"
            placeholder="e.g., Enforce session expiration check prior to wire settlement"
            className="input-field"
            {...register('title')}
          />
          {errors.title && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.title.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="cr-description" className="field-label">
            Change Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="cr-description"
            rows={4}
            placeholder="Provide technical details about modified APIs, validations, database rules, or business logic..."
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
          <span className="field-label">
            Affected Modules <span className="text-red-500">*</span>
          </span>
          {modulesQuery.isLoading ? (
            <div className="flex items-center gap-2 rounded-md border border-app-border p-3 text-xs text-app-text-secondary">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading project modules...
            </div>
          ) : projectModules.length === 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
              This project has no modules yet. Add modules on the Projects page before submitting a change request.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2 rounded-md border border-app-border p-3 sm:grid-cols-2">
              {projectModules.map((mod) => {
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
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{mod.name}</p>
                      {mod.description && (
                        <p className="truncate text-[11px] text-app-text-secondary">
                          {mod.description}
                        </p>
                      )}
                    </div>
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
            disabled={isSubmitting || projectModules.length === 0}
            className="btn-primary"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEditing ? 'Save Changes' : 'Create Change Request'}
          </button>
        </div>
      </form>
    </Modal>
  );
};

