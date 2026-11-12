import { apiClient } from './api';
import type { IndexResponse } from '../types/api';

export const ragService = {
  async indexProject(projectId: number): Promise<IndexResponse> {
    const response = await apiClient.post<IndexResponse>(
      '/rag/index',
      { project_id: projectId },
      { timeout: 120000 }
    );
    return response.data;
  },
};

