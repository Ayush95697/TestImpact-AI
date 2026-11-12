import { apiClient } from './api';
import type {
  DashboardSummaryResponse,
  HealthResponse,
  SystemCapabilitiesResponse,
} from '../types/api';

export const systemService = {
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/health', { timeout: 5000 });
    return response.data;
  },

  async getCapabilities(): Promise<SystemCapabilitiesResponse> {
    const response = await apiClient.get<SystemCapabilitiesResponse>('/system/capabilities', {
      timeout: 5000,
    });
    return response.data;
  },

  async getDashboardSummary(): Promise<DashboardSummaryResponse> {
    const response = await apiClient.get<DashboardSummaryResponse>('/dashboard/summary');
    return response.data;
  },
};

