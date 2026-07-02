/* eslint-disable react/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
} from 'react'
import type { ReactNode } from 'react'
import { schemaService } from '../services/schema'
import { useNotifications } from './NotificationContext'

export interface Column {
  id: string
  name: string
  type: string
  isPrimaryKey: boolean
  isNullable: boolean
  defaultValue: string
}

export interface Table {
  id: string
  name: string
  columns: Column[]
}

export interface Relationship {
  id: string
  name: string
  sourceTableId: string
  sourceColumnId: string
  targetTableId: string
  targetColumnId: string
  type: 'one-to-one' | 'one-to-many' | 'many-to-one' | 'many-to-many'
  isRequired: boolean
  cascadeDelete: boolean
  cascadeUpdate: boolean
}

interface SchemaContextType {
  tables: Table[]
  setTables: React.Dispatch<React.SetStateAction<Table[]>>
  relationships: Relationship[]
  setRelationships: React.Dispatch<React.SetStateAction<Relationship[]>>
  isLoading: boolean
  isSaving: boolean
  saveStatus: 'saving' | 'saved' | 'failed' | 'idle'
  triggerSave: () => Promise<void>
}

const SchemaContext = createContext<SchemaContextType | undefined>(undefined)

export const SchemaProvider = ({ children }: { children: ReactNode }) => {
  const [tables, setTables] = useState<Table[]>([])
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'saving' | 'saved' | 'failed' | 'idle'>('idle')
  const { addNotification } = useNotifications()

  const isLoadedRef = useRef(false)

  // 1. Load schema from backend on startup
  useEffect(() => {
    const fetchSchema = async () => {
      try {
        setIsLoading(true)
        const response = await schemaService.loadSchema()
        if (response.success && response.data) {
          setTables(response.data.tables)
          setRelationships(response.data.relationships)
          addNotification({
            type: 'success',
            title: 'Schema Registry Loaded',
            message: 'Database schema configuration loaded from backend successfully.',
          })
        } else {
          addNotification({
            type: 'warning',
            title: 'Offline Schema Mode',
            message:
              response.error?.message ||
              'Could not load schema. Initializing with local designer layout.',
          })
        }
      } catch (err: any) {
        addNotification({
          type: 'error',
          title: 'Connection Failure',
          message:
            err.message ||
            'Failed to establish backend handshake. Running in offline mockup mode.',
        })
      } finally {
        isLoadedRef.current = true
        setIsLoading(false)
      }
    }
    fetchSchema()
  }, [addNotification])

  // Explicit Save manual function
  const triggerSave = async () => {
    try {
      setIsSaving(true)
      setSaveStatus('saving')
      const response = await schemaService.saveSchema({ tables, relationships })
      if (!response.success) {
        setSaveStatus('failed')
        addNotification({
          type: 'error',
          title: 'Manual Save Failed',
          message: response.error?.message || 'Server rejected schema updates.',
        })
      } else {
        setSaveStatus('saved')
        addNotification({
          type: 'success',
          title: 'Schema Saved',
          message: 'All relational tables and links persisted to backend database.',
        })
      }
    } catch (err: any) {
      setSaveStatus('failed')
      addNotification({
        type: 'error',
        title: 'Network Timeout',
        message: err.message || 'Auto-save offline.',
      })
    } finally {
      setIsSaving(false)
    }
  }

  // 2. Debounced Auto-Save on state updates
  useEffect(() => {
    if (!isLoadedRef.current) return

    setSaveStatus('saving')
    const timer = setTimeout(async () => {
      try {
        setIsSaving(true)
        const response = await schemaService.saveSchema({ tables, relationships })
        if (!response.success) {
          setSaveStatus('failed')
          addNotification({
            type: 'warning',
            title: 'Persist Failure',
            message: response.error?.message || 'Failed to auto-save schema.',
          })
        } else {
          setSaveStatus('saved')
        }
      } catch {
        setSaveStatus('failed')
      } finally {
        setIsSaving(false)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [tables, relationships, addNotification])

  return (
    <SchemaContext.Provider
      value={{
        tables,
        setTables,
        relationships,
        setRelationships,
        isLoading,
        isSaving,
        saveStatus,
        triggerSave,
      }}
    >
      {children}
    </SchemaContext.Provider>
  )
}

export const useSchema = () => {
  const context = useContext(SchemaContext)
  if (!context) throw new Error('useSchema must be used within SchemaProvider')
  return context
}
