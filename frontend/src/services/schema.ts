import { apiClient } from '../api/client'
import type { ApiResponse } from '../types/api'
import type { Table, Relationship } from '../context/SchemaContext'

export interface ValidationResult {
  id: string
  category:
    | 'Tables'
    | 'Columns'
    | 'Relationships'
    | 'Naming'
    | 'Constraints'
    | 'Data Types'
  severity: 'Passed' | 'Info' | 'Warning' | 'Error'
  title: string
  description: string
  suggestedFix: string
}

export const schemaService = {
  loadSchema: async (): Promise<
    ApiResponse<{ tables: Table[]; relationships: Relationship[] }>
  > => {
    return apiClient.get<{ tables: Table[]; relationships: Relationship[] }>(
      '/schema'
    )
  },

  saveSchema: async (schema: {
    tables: Table[]
    relationships: Relationship[]
  }): Promise<ApiResponse<{ status: string; message: string }>> => {
    return apiClient.post<{ status: string; message: string }>(
      '/schema',
      schema
    )
  },

  validateSchema: async (schema: {
    tables: Table[]
    relationships: Relationship[]
  }): Promise<ApiResponse<ValidationResult[]>> => {
    return apiClient.post<ValidationResult[]>('/schema/validate', schema)
  },

  aiSchemaAssistant: async (schema: {
    tables: Table[]
    relationships: Relationship[]
  }): Promise<ApiResponse<AIAssistantReport>> => {
    return apiClient.post<AIAssistantReport>('/schema/ai-assist', schema)
  },

  startGeneration: async (payload: {
    schemaState: { tables: Table[]; relationships: Relationship[] }
    rowTargets: Record<string, number>
    seed?: number | null
    batchSize: number
    outputFormat: string
  }): Promise<ApiResponse<GenerationResponse>> => {
    return apiClient.post<GenerationResponse>('/schema/generate', payload)
  },

  getGenerationStatus: async (workflowId: string): Promise<ApiResponse<GenerationResponse>> => {
    return apiClient.get<GenerationResponse>(`/schema/generate/${workflowId}`)
  },

  cancelGeneration: async (workflowId: string): Promise<ApiResponse<{ status: string; message: string }>> => {
    return apiClient.post<{ status: string; message: string }>(`/schema/generate/${workflowId}/cancel`)
  },

  listJobs: async (filters?: {
    status?: string
    job_type?: string
    search?: string
  }): Promise<ApiResponse<Job[]>> => {
    let query = ''
    if (filters) {
      const params = new URLSearchParams()
      if (filters.status) params.append('status', filters.status)
      if (filters.job_type) params.append('job_type', filters.job_type)
      if (filters.search) params.append('search', filters.search)
      const qStr = params.toString()
      if (qStr) query = `?${qStr}`
    }
    return apiClient.get<Job[]>(`/schema/jobs${query}`)
  },

  getJobDetails: async (jobId: string): Promise<ApiResponse<Job>> => {
    return apiClient.get<Job>(`/schema/jobs/${jobId}`)
  },

  cancelJob: async (jobId: string): Promise<ApiResponse<{ status: string; message: string }>> => {
    return apiClient.post<{ status: string; message: string }>(`/schema/jobs/${jobId}/cancel`)
  },
}

export interface AISuggestion {
  id: string
  category: 'Naming' | 'Relationships' | 'Performance' | 'Validation' | 'Best Practices'
  severity: 'low' | 'medium' | 'high'
  title: string
  explanation: string
  suggestedAction?: string
}

export interface AIAssistantReport {
  status: 'Completed' | 'Failed'
  summary: string
  suggestions: AISuggestion[]
  executionDurationMs: number
}

export interface TableProgress {
  tableName: string
  status: 'Pending' | 'Running' | 'Completed' | 'Failed'
  rowsGenerated: number
  targetRows: number
  error?: string
}

export interface GenerationResponse {
  workflowId: string
  status: 'Queued' | 'Running' | 'Completed' | 'Failed'
  progress: TableProgress[]
  totalRowsGenerated: number
  durationMs: number
  errors: string[]
  downloadPlaceholder?: string
}

export interface Job {
  jobId: string
  type: string
  status: 'Queued' | 'Running' | 'Completed' | 'Failed' | 'Cancelled'
  startedAt: string
  finishedAt?: string | null
  duration: number
  progress: number
  owner: string
  resultSummary?: string | null
  errorMessage?: string | null
  details: {
    progress?: TableProgress[]
    [key: string]: any
  }
}



