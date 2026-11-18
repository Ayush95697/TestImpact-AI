import { apiClient } from './api';
import type {
  AnalyzePullRequestRequest,
  AnalyzePullRequestResponse,
  GitHubConnectionResponse,
  ImportedPullRequest,
  Repository,
  RepositoryCreate,
} from '../types/api';

export const githubService = {
  async listRepositories(): Promise<Repository[]> {
    const response = await apiClient.get<Repository[]>('/repositories');
    return response.data;
  },

  async createRepository(payload: RepositoryCreate): Promise<Repository> {
    const response = await apiClient.post<Repository>('/repositories', payload);
    return response.data;
  },

  async deleteRepository(repositoryId: number): Promise<void> {
    await apiClient.delete(`/repositories/${repositoryId}`);
  },

  async checkConnection(repository?: string): Promise<GitHubConnectionResponse> {
    const response = await apiClient.get<GitHubConnectionResponse>('/github/connection', {
      params: repository ? { repository } : undefined,
    });
    return response.data;
  },

  async analyzePullRequest(payload: AnalyzePullRequestRequest): Promise<AnalyzePullRequestResponse> {
    const response = await apiClient.post<AnalyzePullRequestResponse>('/analyze-pr', payload);
    return response.data;
  },

  async getImportedPullRequest(
    repositoryId: number,
    prNumber: number
  ): Promise<ImportedPullRequest> {
    const response = await apiClient.get<ImportedPullRequest>(
      `/repositories/${repositoryId}/pull-requests/${prNumber}`
    );
    return response.data;
  },
};
