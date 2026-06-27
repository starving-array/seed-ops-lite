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

