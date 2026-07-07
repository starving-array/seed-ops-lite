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
    outputFormat: string
  }): Promise<ApiResponse<GenerationResponse>> => {
    return apiClient.post<GenerationResponse>('/schema/generate', payload)
  },

  getGenerationStatus: async (workflowId: string): Promise<ApiResponse<GenerationResponse>> => {
    return apiClient.get<GenerationResponse>(`/schema/generate/${workflowId}`)
  },

  getPreviewData: async (workflowId: string): Promise<ApiResponse<Record<string, any[]>>> => {
    return apiClient.get<Record<string, any[]>>(`/schema/generate/${workflowId}/preview`)
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

  listExportableDatasets: async (): Promise<ApiResponse<ExportableDataset[]>> => {
    return apiClient.get<ExportableDataset[]>('/schema/export/datasets')
  },

  startExport: async (payload: ExportSettings): Promise<ApiResponse<Job>> => {
    return apiClient.post<Job>('/schema/export', payload)
  },

  importSchema: async (payload: {
    content?: string
    fileType?: string
    file?: File
  }): Promise<ApiResponse<{ tables: Table[]; relationships: Relationship[] }>> => {
    const formData = new FormData()
    if (payload.content) formData.append('content', payload.content)
    if (payload.fileType) formData.append('file_type', payload.fileType)
    if (payload.file) formData.append('file', payload.file)
    return apiClient.post<{ tables: Table[]; relationships: Relationship[] }>(
      '/schema/import',
      formData
    )
  },

  getStats: async (): Promise<ApiResponse<{
    projects_count: number
    schemas_count: number
    total_generated_rows: number
    jobs_count: number
    exports_count: number
    validation_statistics: {
      total_runs: number
      passed: number
      failed: number
    }
    token_usage: {
      total_tokens: number
      input_tokens: number
      output_tokens: number
      tokens_per_job: number
      active_model: string
      active_provider: string
      estimated_cost_usd: number
    }
  }>> => {
    return apiClient.get('/schema/stats')
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

export interface LLMDiagnosticUsage {
  promptTokens: number | null
  completionTokens: number | null
  totalTokens: number | null
}

export interface LLMSessionDiagnostics {
  provider: string
  model: string
  totalLatencyMs: number | null
  attemptNumber: number | null
  maxAttempts: number | null
  totalRetries: number | null
  finishReason: string | null
  responseType: string | null
  usage: LLMDiagnosticUsage | null
  aiStatus?: string | null
}

export interface LLMDiagnostics {
  provider: string
  model: string
  latencyMs: number | null
  attemptNumber: number | null
  maxAttempts: number | null
  retryCount: number | null
  finishReason: string | null
  responseType: string | null
  usage: LLMDiagnosticUsage | null
  skillName?: string | null
  status?: string | null
  providerErrorCode?: number | null
  providerStatus?: string | null
  providerMessage?: string | null
}

export interface AIAssistantReport {
  status: 'Completed' | 'Failed'
  summary: string
  suggestions: AISuggestion[]
  executionDurationMs: number
  result?: AIAssistantReport
  diagnostics?: LLMDiagnostics | null
  sessionDiagnostics?: LLMSessionDiagnostics | null
  skills?: LLMDiagnostics[] | null
  workflowStatus?: string | null
  aiStatus?: string | null
  validationStatus?: string | null
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
  owner?: string | null
  resultSummary?: string | null
  errorMessage?: string | null
  details: {
    progress?: TableProgress[]
    [key: string]: any
  }
}

export interface ExportableDataset {
  workflowId: string
  startedAt: string
  finishedAt: string
  totalRowsGenerated: number
  resultSummary: string
  progress: TableProgress[]
}

export interface ExportSettings {
  workflowId: string
  format: 'csv' | 'json' | 'sql'
  tables: string[]
  singleFile: boolean
  compression: boolean
  includeMetadata: boolean
  fileNameConvention: 'default' | 'timestamp'
}




