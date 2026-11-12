import { apiClient } from './api';
import type { Defect, DefectCreate, DefectUpdate } from '../types/api';

export const defectService = {
  async listDefects(filters?: {
    project_id?: number;
    module_id?: number;
  }): Promise<Defect[]> {
    const response = await apiClient.get<Defect[]>('/defects', { params: filters });
    return response.data;
  },

  async getDefect(defectId: number): Promise<Defect> {
    const response = await apiClient.get<Defect>(`/defects/${defectId}`);
    return response.data;
  },

  async createDefect(payload: DefectCreate): Promise<Defect> {
    const response = await apiClient.post<Defect>('/defects', payload);
    return response.data;
  },

  async updateDefect(defectId: number, payload: DefectUpdate): Promise<Defect> {
    const response = await apiClient.patch<Defect>(`/defects/${defectId}`, payload);
    return response.data;
  },

  async deleteDefect(defectId: number): Promise<void> {
    await apiClient.delete(`/defects/${defectId}`);
  },
};

