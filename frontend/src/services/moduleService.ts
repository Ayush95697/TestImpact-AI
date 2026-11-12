import { apiClient } from './api';
import type { ModuleCreate, ModuleItem, ModuleUpdate } from '../types/api';

export const moduleService = {
  async listByProject(projectId: number): Promise<ModuleItem[]> {
    const response = await apiClient.get<ModuleItem[]>(`/projects/${projectId}/modules`);
    return response.data;
  },

  async getModule(moduleId: number): Promise<ModuleItem> {
    const response = await apiClient.get<ModuleItem>(`/modules/${moduleId}`);
    return response.data;
  },

  async createModule(projectId: number, payload: ModuleCreate): Promise<ModuleItem> {
    const response = await apiClient.post<ModuleItem>(
      `/projects/${projectId}/modules`,
      payload
    );
    return response.data;
  },

  async updateModule(moduleId: number, payload: ModuleUpdate): Promise<ModuleItem> {
    const response = await apiClient.patch<ModuleItem>(`/modules/${moduleId}`, payload);
    return response.data;
  },

  async deleteModule(moduleId: number): Promise<void> {
    await apiClient.delete(`/modules/${moduleId}`);
  },
};

