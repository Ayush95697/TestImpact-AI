import { apiClient } from './api';
import type {
  AnalysisResponse,
  AnalysisRunDetail,
  AnalysisRunListResponse,
  Recommendation,
} from '../types/api';

export interface ListAnalysisRunsParams {
  project_id?: number;
  change_request_id?: number;
  status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const analysisService = {
  async triggerAnalysis(changeRequestId: number, topK = 10): Promise<AnalysisResponse> {
    const response = await apiClient.post<AnalysisResponse>(
      `/change-requests/${changeRequestId}/analyze`,
      { top_k: topK },
      { timeout: 60000 }
    );
    return response.data;
  },

  async listAnalysisRuns(params?: ListAnalysisRunsParams): Promise<AnalysisRunListResponse> {
    const response = await apiClient.get<AnalysisRunListResponse>('/analysis-runs', {
      params,
    });
    return response.data;
  },

  async getAnalysisRun(analysisRunId: number): Promise<AnalysisRunDetail> {
    const response = await apiClient.get<AnalysisRunDetail>(
      `/analysis-runs/${analysisRunId}`
    );
    return response.data;
  },

  async reviewRecommendation(
    recommendationId: number,
    reviewStatus: 'accepted' | 'rejected'
  ): Promise<Recommendation> {
    const response = await apiClient.patch<Recommendation>(
      `/recommendations/${recommendationId}/review`,
      { review_status: reviewStatus }
    );
    return response.data;
  },
};

