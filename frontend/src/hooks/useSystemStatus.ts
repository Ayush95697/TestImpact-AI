import { useQuery } from '@tanstack/react-query';
import { systemService } from '../services/systemService';
import type { SystemCapabilitiesResponse } from '../types/api';

export function useBackendHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => systemService.getHealth(),
    refetchInterval: 30000,
    retry: 1,
    staleTime: 10000,
  });
}

const SAFE_DEFAULT_CAPABILITIES: SystemCapabilitiesResponse = {
  rag_available: false,
  llm_explanations_available: false,
};

export function useSystemCapabilities() {
  return useQuery({
    queryKey: ['system', 'capabilities'],
    queryFn: async (): Promise<SystemCapabilitiesResponse> => {
      try {
        return await systemService.getCapabilities();
      } catch {
        // Fail safely so optional LLM/RAG controls hide if capabilities cannot be confirmed
        return SAFE_DEFAULT_CAPABILITIES;
      }
    },
    refetchInterval: 60000,
    retry: false,
    staleTime: 30000,
  });
}

