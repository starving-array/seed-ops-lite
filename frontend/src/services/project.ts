import { apiClient } from '../api/client'
import type { ApiResponse } from '../types/api'
import type { Project } from '../types/project'

export const projectService = {
  getProjects: async (): Promise<ApiResponse<Project[]>> => {
    return apiClient.get<Project[]>('/projects')
  },

  createProject: async (project: {
    id: string
    name: string
    description?: string
    status?: string
  }): Promise<ApiResponse<Project>> => {
    return apiClient.post<Project>('/projects', project)
  },
}
