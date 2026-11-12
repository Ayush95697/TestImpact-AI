import { apiClient } from './api';
import type { Project, ProjectCreate, ProjectUpdate } from '../types/api';

export const projectService = {
  async listProjects(): Promise<Project[]> {
    const response = await apiClient.get<Project[]>('/projects');
    return response.data;
  },

  async getProject(projectId: number): Promise<Project> {
    const response = await apiClient.get<Project>(`/projects/${projectId}`);
    return response.data;
  },

  async createProject(payload: ProjectCreate): Promise<Project> {
    const response = await apiClient.post<Project>('/projects', payload);
    return response.data;
  },

  async updateProject(projectId: number, payload: ProjectUpdate): Promise<Project> {
    const response = await apiClient.patch<Project>(`/projects/${projectId}`, payload);
    return response.data;
  },

  async deleteProject(projectId: number): Promise<void> {
    await apiClient.delete(`/projects/${projectId}`);
  },
};

