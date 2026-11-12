import { apiClient, ApiError } from './api';
import type { AnalysisExplanation } from '../types/api';

export const llmService = {
  async generateExplanation(analysisRunId: number): Promise<AnalysisExplanation> {
    const response = await apiClient.post<AnalysisExplanation>(
      `/analysis-runs/${analysisRunId}/explain`,
      undefined,
      { timeout: 75000 }
    );
    return response.data;
  },

  async getExplanation(analysisRunId: number): Promise<AnalysisExplanation | null> {
    try {
      const response = await apiClient.get<AnalysisExplanation>(
        `/analysis-runs/${analysisRunId}/explanation`
      );
      return response.data;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return null;
      }
      throw error;
    }
  },
};

