import { apiClient } from './api';
import type { TestExecution, TestExecutionCreate } from '../types/api';

export const testExecutionService = {
  async listExecutions(filters?: {
    test_case_id?: number;
    project_id?: number;
  }): Promise<TestExecution[]> {
    const response = await apiClient.get<TestExecution[]>('/test-executions', {
      params: filters,
    });
    return response.data;
  },

  async getExecution(executionId: number): Promise<TestExecution> {
    const response = await apiClient.get<TestExecution>(`/test-executions/${executionId}`);
    return response.data;
  },

  async createExecution(payload: TestExecutionCreate): Promise<TestExecution> {
    const response = await apiClient.post<TestExecution>('/test-executions', payload);
    return response.data;
  },
};

