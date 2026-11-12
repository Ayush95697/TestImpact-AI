import { apiClient } from './api';
import type {
  ChangeRequest,
  ChangeRequestCreate,
  ChangeRequestUpdate,
} from '../types/api';

export const changeRequestService = {
  async listChangeRequests(filters?: {
    project_id?: number;
    module_id?: number;
  }): Promise<ChangeRequest[]> {
    const response = await apiClient.get<ChangeRequest[]>('/change-requests', {
      params: filters,
    });
    return response.data;
  },

  async getChangeRequest(changeRequestId: number): Promise<ChangeRequest> {
    const response = await apiClient.get<ChangeRequest>(
      `/change-requests/${changeRequestId}`
    );
    return response.data;
  },

  async createChangeRequest(payload: ChangeRequestCreate): Promise<ChangeRequest> {
    const response = await apiClient.post<ChangeRequest>('/change-requests', payload);
    return response.data;
  },

  async updateChangeRequest(
    changeRequestId: number,
    payload: ChangeRequestUpdate
  ): Promise<ChangeRequest> {
    const response = await apiClient.patch<ChangeRequest>(
      `/change-requests/${changeRequestId}`,
      payload
    );
    return response.data;
  },

  async deleteChangeRequest(changeRequestId: number): Promise<void> {
    await apiClient.delete(`/change-requests/${changeRequestId}`);
  },
};

