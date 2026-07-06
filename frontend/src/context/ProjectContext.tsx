import {
  createContext,
  useContext,
  useState,
  useEffect,
} from 'react'
import type { ReactNode } from 'react'
import { projectService } from '../services/project'
import type { Project } from '../types/project'
import { useNotifications } from './NotificationContext'

interface ProjectContextType {
  projects: Project[]
  activeProjectId: string
  activeProject: Project | null
  loading: boolean
  fetchProjects: () => Promise<void>
  selectProject: (id: string) => void
  createProject: (name: string, description: string) => Promise<Project | null>
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string>(
    localStorage.getItem('active_project_id') || 'default'
  )
  const [loading, setLoading] = useState(true)
  const { addNotification } = useNotifications()

  const fetchProjects = async () => {
    try {
      setLoading(true)
      const res = await projectService.getProjects()
      if (res.success && res.data) {
        setProjects(res.data)
      } else {
        addNotification({
          type: 'warning',
          title: 'Project Service Offline',
          message: res.error?.message || 'Could not fetch projects.',
        })
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Project Fetch Failure',
        message: err.message || 'Failed to connect to projects service.',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  const selectProject = (id: string) => {
    localStorage.setItem('active_project_id', id)
    setActiveProjectId(id)
    addNotification({
      type: 'success',
      title: 'Project Selected',
      message: `Active workspace switched to project '${id}'.`,
    })
  }

  const createProject = async (name: string, description: string) => {
    try {
      const id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || Math.random().toString(36).substring(2, 9)
      const res = await projectService.createProject({ id, name, description })
      if (res.success && res.data) {
        setProjects((prev) => [res.data!, ...prev])
        addNotification({
          type: 'success',
          title: 'Project Created',
          message: `Project '${name}' has been created and persisted successfully.`,
        })
        return res.data
      } else {
        addNotification({
          type: 'error',
          title: 'Project Creation Failed',
          message: res.error?.message || 'Could not create project.',
        })
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Project Creation Error',
        message: err.message || 'An error occurred during project creation.',
      })
    }
    return null
  }

  const activeProject = projects.find((p) => p.id === activeProjectId) || null

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProjectId,
        activeProject,
        loading,
        fetchProjects,
        selectProject,
        createProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  )
}

export const useProjects = () => {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProjects must be used within a ProjectProvider')
  }
  return context
}
