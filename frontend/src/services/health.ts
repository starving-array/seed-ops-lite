import { apiClient } from '../api/client'
import type { ApiResponse } from '../types/api'

export interface SQLiteStatus {
  status: string
  migration_version: string
  database_path: string
  connection_status: string
  initialized: boolean
  migration_status: string
  pending_migrations: string[]
  last_successful_migration_at: string | null
  database_size_bytes: number
}

export interface RuntimeStatus {
  provider: string
  redis_status: string
  connection_status: string
  reconnect_count: number
  mode: string
  last_reconnection_time: string | null
  recovering: boolean
  memory_entries?: number
  memory_capacity?: number
  memory_utilization?: number
  evicted_entries?: number
  expired_entries_removed?: number
  cleanup_runs?: number
  last_cleanup?: string | null
}

export interface ServiceStatus {
  status: string
  details?: string | null
}

export interface LLMConfigStatus {
  provider: string
  model: string
  gateway_status: string
  retry_count: number
  timeout: number
  api_key_configured: boolean
}

export interface RepositoryStatus {
  git_branch: string
  quality_gates: string
  verification_stamp: string
  working_tree_status: string
  merge_conflicts: string
}

export interface PerformanceMetrics {
  sqlite_latency_ms: number
  redis_latency_ms: number | null
}

export interface HealthReport {
  status: string
  version: string
  environment: string
  uptime: number
  python_version: string
  redis_status: string
  startup_time: string
  storage_mode: string
  sqlite_status: SQLiteStatus
  runtime_status: RuntimeStatus
  services: Record<string, ServiceStatus>
  debug_mode: boolean
  llm_status: LLMConfigStatus
  repository_status: RepositoryStatus
  performance_metrics: PerformanceMetrics
}

export const healthService = {
  checkStatus: async (): Promise<ApiResponse<HealthReport>> => {
    return apiClient.get<HealthReport>('/health')
  },
}

