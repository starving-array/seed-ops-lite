import { apiClient } from '../api/client'
import type { ApiResponse } from '../types/api'

export interface HealthReport {
  status: string
  version: string
  redis: string
  storage_mode?: string
}

export const healthService = {
  checkStatus: async (): Promise<ApiResponse<HealthReport>> => {
    return apiClient.get<HealthReport>('/health')
  },
}
