import { apiClient } from './api';
import type { TestCase, TestCaseCreate, TestCaseUpdate } from '../types/api';

export const testCaseService = {
  async listTestCases(filters?: {
    project_id?: number;
    module_id?: number;
  }): Promise<TestCase[]> {
    const response = await apiClient.get<TestCase[]>('/test-cases', { params: filters });
    return response.data;
  },

  async getTestCase(testCaseId: number): Promise<TestCase> {
    const response = await apiClient.get<TestCase>(`/test-cases/${testCaseId}`);
    return response.data;
  },

  async createTestCase(payload: TestCaseCreate): Promise<TestCase> {
    const response = await apiClient.post<TestCase>('/test-cases', payload);
    return response.data;
  },

  async updateTestCase(testCaseId: number, payload: TestCaseUpdate): Promise<TestCase> {
    const response = await apiClient.patch<TestCase>(`/test-cases/${testCaseId}`, payload);
    return response.data;
  },

  async deleteTestCase(testCaseId: number): Promise<void> {
    await apiClient.delete(`/test-cases/${testCaseId}`);
  },
};

