import { useState, useEffect } from 'react'
import {
  Button,
  Card,
  Alert,
  Divider,
  PageHeader,
  EmptyState,
  Spinner,
} from '../../components/ui'
import { useSchema } from '../../context/SchemaContext'
import type { Table, Column, Relationship } from '../../context/SchemaContext'
import { schemaService } from '../../services/schema'
import type { AISuggestion } from '../../services/schema'
import { useProjects } from '../../context/ProjectContext'

export const SchemaGenerator = () => {
  const {
    tables,
    setTables,
    relationships,
    setRelationships,
    isLoading,
    isSaving,
    saveStatus,
    triggerSave,
  } = useSchema()

  const { projects, activeProjectId, selectProject } = useProjects()

  const [selectedTableId, setSelectedTableId] = useState<string>('1')
  const [tableSearch, setTableSearch] = useState<string>('')

  // Import Schema states
  const [isImportOpen, setIsImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importFileType, setImportFileType] = useState('sql')
  const [isDragging, setIsDragging] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [importError, setImportError] = useState('')

  const handleImportSchema = async () => {
    setIsImporting(true)
    setImportError('')
    try {
      const response = await schemaService.importSchema({
        content: importFile ? undefined : importText,
        fileType: importFileType,
        file: importFile || undefined,
      })

      if (response.success && response.data) {
        setTables(response.data.tables)
        setRelationships(response.data.relationships)
        setIsImportOpen(false)
        setImportText('')
        setImportFile(null)
      } else {
        setImportError(response.error?.message || 'Failed to import schema.')
      }
    } catch (err: any) {
      setImportError(err.message || 'An error occurred during schema import.')
    } finally {
      setIsImporting(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0]
      setImportFile(file)
      const ext = file.name.split('.').pop()?.toLowerCase() || ''
      if (['sql', 'ddl', 'csv', 'xlsx', 'json', 'txt'].includes(ext)) {
        setImportFileType(ext)
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0]
      setImportFile(file)
      const ext = file.name.split('.').pop()?.toLowerCase() || ''
      if (['sql', 'ddl', 'csv', 'xlsx', 'json', 'txt'].includes(ext)) {
        setImportFileType(ext)
      }
    }
  }

  // AI Schema Assistant state
  const [aiStatus, setAiStatus] = useState<'waiting' | 'analyzing' | 'completed' | 'failed'>('waiting')
  const [aiSummary, setAiSummary] = useState('')
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion[]>([])
  const [aiExecutionTime, setAiExecutionTime] = useState(0)
  const [aiErrorMessage, setAiErrorMessage] = useState('')
  const [acceptedSuggestions, setAcceptedSuggestions] = useState<string[]>([])
  const [dismissedSuggestions, setDismissedSuggestions] = useState<string[]>([])
  const [ignoredSuggestions, setIgnoredSuggestions] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('All')

  const handleAIAnalysis = async () => {
    setAiStatus('analyzing')
    setAiErrorMessage('')
    setAcceptedSuggestions([])
    setDismissedSuggestions([])

    try {
      const response = await schemaService.aiSchemaAssistant({
        tables,
        relationships,
      })

      if (response.success && response.data) {
        if (response.data.status === 'Completed') {
          setAiSuggestions(response.data.suggestions)
          setAiSummary(response.data.summary)
          setAiExecutionTime(response.data.executionDurationMs)
          setAiStatus('completed')
        } else {
          setAiErrorMessage(response.data.summary || 'AI Analysis returned failed status.')
          setAiStatus('failed')
        }
      } else {
        setAiErrorMessage(response.error?.message || 'Failed to communicate with AI Assistant backend.')
        setAiStatus('failed')
      }
    } catch (err: any) {
      setAiErrorMessage(err.message || 'An unexpected error occurred during AI analysis.')
      setAiStatus('failed')
    }
  }

  const handleAcceptSuggestion = (id: string) => {
    setAcceptedSuggestions((prev) => [...prev, id])
  }

  const handleDismissSuggestion = (id: string) => {
    setDismissedSuggestions((prev) => [...prev, id])
  }

  const handleIgnoreSuggestion = (id: string) => {
    setIgnoredSuggestions((prev) => [...prev, id])
  }

  // New relationship form state
  const [newRelName, setNewRelName] = useState('')
  const [newRelSourceTable, setNewRelSourceTable] = useState('')
  const [newRelSourceCol, setNewRelSourceCol] = useState('')
  const [newRelTargetTable, setNewRelTargetTable] = useState('')
  const [newRelTargetCol, setNewRelTargetCol] = useState('')
  const [newRelType, setNewRelType] = useState<
    'one-to-one' | 'one-to-many' | 'many-to-one' | 'many-to-many'
  >('many-to-one')
  const [newRelIsRequired, setNewRelIsRequired] = useState(true)

  const selectedTable = tables.find((t) => t.id === selectedTableId)

  // Initialize and Sync Relationship Form Defaults
  useEffect(() => {
    if (selectedTable) {
      setNewRelSourceTable(selectedTable.id)
      if (selectedTable.columns.length > 0) {
        setNewRelSourceCol(selectedTable.columns[0].id)
      } else {
        setNewRelSourceCol('')
      }
    }
  }, [selectedTableId, selectedTable])

  // Sync target defaults
  useEffect(() => {
    if (tables.length > 0) {
      const otherTable =
        tables.find((t) => t.id !== newRelSourceTable) || tables[0]
      setNewRelTargetTable(otherTable.id)
      if (otherTable.columns.length > 0) {
        setNewRelTargetCol(otherTable.columns[0].id)
      } else {
        setNewRelTargetCol('')
      }
    }
  }, [newRelSourceTable, tables])

  // Sync source columns list
  useEffect(() => {
    const sTable = tables.find((t) => t.id === newRelSourceTable)
    if (sTable && sTable.columns.length > 0) {
      setNewRelSourceCol(sTable.columns[0].id)
    }
  }, [newRelSourceTable, tables])

  // Sync target columns list
  useEffect(() => {
    const tTable = tables.find((t) => t.id === newRelTargetTable)
    if (tTable && tTable.columns.length > 0) {
      setNewRelTargetCol(tTable.columns[0].id)
    }
  }, [newRelTargetTable, tables])

  // Auto-generate name
  useEffect(() => {
    const sTable = tables.find((t) => t.id === newRelSourceTable)
    const tTable = tables.find((t) => t.id === newRelTargetTable)
    const sCol = sTable?.columns.find((c) => c.id === newRelSourceCol)
    const tCol = tTable?.columns.find((c) => c.id === newRelTargetCol)

    if (sTable && sCol && tTable && tCol) {
      setNewRelName(`fk_${sTable.name}_${sCol.name}`)
    }
  }, [
    newRelSourceTable,
    newRelSourceCol,
    newRelTargetTable,
    newRelTargetCol,
    tables,
  ])

  // Actions
  const handleAddTable = () => {
    const name = prompt('Enter Table Name:')
    if (!name) return
    const normalized = name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '_')
    if (tables.some((t) => t.name.toLowerCase() === normalized)) {
      alert('Table name already exists.')
      return
    }
    const newTable: Table = {
      id: Math.random().toString(36).substring(2, 9),
      name: normalized,
      columns: [
        {
          id: Math.random().toString(36).substring(2, 9),
          name: 'id',
          type: 'INTEGER',
          isPrimaryKey: true,
          isNullable: false,
          defaultValue: '',
        },
      ],
    }
    setTables((prev) => [...prev, newTable])
    setSelectedTableId(newTable.id)
  }

  const handleRenameTable = (tableId: string) => {
    const table = tables.find((t) => t.id === tableId)
    if (!table) return
    const name = prompt('Rename Table:', table.name)
    if (!name) return
    const normalized = name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '_')
    if (normalized === table.name) return
    if (
      tables.some(
        (t) => t.id !== tableId && t.name.toLowerCase() === normalized
      )
    ) {
      alert('Table name already exists.')
      return
    }
    setTables((prev) =>
      prev.map((t) => (t.id === tableId ? { ...t, name: normalized } : t))
    )
  }

  const handleDeleteTable = (tableId: string) => {
    if (!confirm('Are you sure you want to delete this table?')) return
    setTables((prev) => prev.filter((t) => t.id !== tableId))
    setRelationships((prev) =>
      prev.filter((r) => r.sourceTableId !== tableId && r.targetTableId !== tableId)
    )
    if (selectedTableId === tableId) {
      const remaining = tables.filter((t) => t.id !== tableId)
      if (remaining.length > 0) {
        setSelectedTableId(remaining[0].id)
      } else {
        setSelectedTableId('')
      }
    }
  }

  const handleAddColumn = (tableId: string) => {
    const name = prompt('Enter Column Name:')
    if (!name) return
    const normalized = name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '_')
    const table = tables.find((t) => t.id === tableId)
    if (!table) return
    if (table.columns.some((c) => c.name.toLowerCase() === normalized)) {
      alert('Column name already exists.')
      return
    }
    const newCol: Column = {
      id: Math.random().toString(36).substring(2, 9),
      name: normalized,
      type: 'VARCHAR',
      isPrimaryKey: false,
      isNullable: true,
      defaultValue: '',
    }
    setTables((prev) =>
      prev.map((t) =>
        t.id === tableId ? { ...t, columns: [...t.columns, newCol] } : t
      )
    )
  }

  const handleRenameColumn = (
    tableId: string,
    columnId: string,
    currentName: string
  ) => {
    const name = prompt('Rename Column:', currentName)
    if (!name) return
    const normalized = name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '_')
    if (normalized === currentName) return
    const table = tables.find((t) => t.id === tableId)
    if (!table) return
    if (
      table.columns.some(
        (c) => c.id !== columnId && c.name.toLowerCase() === normalized
      )
    ) {
      alert('Column name already exists.')
      return
    }
    handleUpdateColumn(tableId, columnId, { name: normalized })
  }

  const handleUpdateColumn = (
    tableId: string,
    columnId: string,
    updates: Partial<Column>
  ) => {
    setTables((prev) =>
      prev.map((t) => {
        if (t.id !== tableId) return t
        return {
          ...t,
          columns: t.columns.map((c) => {
            if (c.id !== columnId) return c
            const nextVal = { ...c, ...updates }
            if (updates.isPrimaryKey) {
              nextVal.isNullable = false
            }
            return nextVal
          }),
        }
      })
    )
  }

  const handleDeleteColumn = (tableId: string, columnId: string) => {
    setTables((prev) =>
      prev.map((t) => {
        if (t.id !== tableId) return t
        return {
          ...t,
          columns: t.columns.filter((c) => c.id !== columnId),
        }
      })
    )
    setRelationships((prev) =>
      prev.filter(
        (r) =>
          !(r.sourceTableId === tableId && r.sourceColumnId === columnId) &&
          !(r.targetTableId === tableId && r.targetColumnId === columnId)
      )
    )
  }

  // Relationship actions
  const handleCreateRelationship = () => {
    if (
      !newRelName ||
      !newRelSourceTable ||
      !newRelSourceCol ||
      !newRelTargetTable ||
      !newRelTargetCol
    ) {
      alert('Please fill in all relationship fields.')
      return
    }

    const isDuplicate = relationships.some(
      (r) =>
        r.sourceTableId === newRelSourceTable &&
        r.sourceColumnId === newRelSourceCol &&
        r.targetTableId === newRelTargetTable &&
        r.targetColumnId === newRelTargetCol
    )
    if (isDuplicate) {
      alert('This relationship configuration already exists.')
      return
    }

    const newRel: Relationship = {
      id: Math.random().toString(36).substring(2, 9),
      name: newRelName,
      sourceTableId: newRelSourceTable,
      sourceColumnId: newRelSourceCol,
      targetTableId: newRelTargetTable,
      targetColumnId: newRelTargetCol,
      type: newRelType,
      isRequired: newRelIsRequired,
      cascadeDelete: false,
      cascadeUpdate: false,
    }

    setRelationships((prev) => [...prev, newRel])
  }

  const handleDeleteRelationship = (relId: string) => {
    setRelationships((prev) => prev.filter((r) => r.id !== relId))
  }

  // Stats
  const totalTables = tables.length
  const totalColumns = tables.reduce((acc, t) => acc + t.columns.length, 0)
  const totalPrimaryKeys = tables.reduce(
    (acc, t) => acc + t.columns.filter((c) => c.isPrimaryKey).length,
    0
  )
  const totalRelationships = relationships.length
  const oneToOneCount = relationships.filter((r) => r.type === 'one-to-one').length
  const oneToManyCount = relationships.filter((r) => r.type === 'one-to-many').length
  const manyToOneCount = relationships.filter((r) => r.type === 'many-to-one').length
  const manyToManyCount = relationships.filter((r) => r.type === 'many-to-many').length

  const tablesWithRelationships = new Set(
    relationships.flatMap((r) => [r.sourceTableId, r.targetTableId])
  )
  const tablesWithoutRelationships = tables.filter(
    (t) => !tablesWithRelationships.has(t.id)
  )

  const filteredTables = tables.filter((t) =>
    t.name.toLowerCase().includes(tableSearch.toLowerCase())
  )

  // Design validation rules
  const schemaWarnings = tables.reduce<string[]>((acc, t) => {
    const hasPk = t.columns.some((c) => c.isPrimaryKey)
    if (!hasPk) {
      acc.push(`Table "${t.name}" has no primary key defined.`)
    }
    if (t.columns.length === 0) {
      acc.push(`Table "${t.name}" has no columns defined.`)
    }
    return acc
  }, [])

  const relationshipWarnings = relationships.reduce<string[]>((acc, r) => {
    const sourceTable = tables.find((t) => t.id === r.sourceTableId)
    const targetTable = tables.find((t) => t.id === r.targetTableId)

    if (!sourceTable) {
      acc.push(`Relationship "${r.name}": Source table no longer exists.`)
      return acc
    }
    if (!targetTable) {
      acc.push(`Relationship "${r.name}": Target table no longer exists.`)
      return acc
    }

    const sourceCol = sourceTable.columns.find((c) => c.id === r.sourceColumnId)
    const targetCol = targetTable.columns.find((c) => c.id === r.targetColumnId)

    if (!sourceCol) {
      acc.push(
        `Relationship "${r.name}": Column "${r.sourceColumnId}" no longer exists in source table "${sourceTable.name}".`
      )
    }
    if (!targetCol) {
      acc.push(
        `Relationship "${r.name}": Column "${r.targetColumnId}" no longer exists in target table "${targetTable.name}".`
      )
    }

    const duplicateInstances = relationships.filter(
      (other) =>
        other.sourceTableId === r.sourceTableId &&
        other.sourceColumnId === r.sourceColumnId &&
        other.targetTableId === r.targetTableId &&
        other.targetColumnId === r.targetColumnId
    )
    if (duplicateInstances.length > 1 && duplicateInstances[0].id === r.id) {
      acc.push(
        `Relationship "${r.name}" has duplicate references to the same fields.`
      )
    }

    return acc
  }, [])

  const allWarnings = [...schemaWarnings, ...relationshipWarnings]

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Spinner size="lg" />
        <span className="text-sm text-slate-400">
          Loading schema configuration from backend...
        </span>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in">
      <div className="flex justify-between items-start flex-wrap gap-4">
        <PageHeader
          title="Schema Designer"
          subtitle="Interactively build entity relationship tables and columns for database generation."
        />
        <div className="flex items-center gap-4 flex-wrap">
          {/* Project Selector */}
          <div className="flex items-center gap-2 bg-slate-900/60 p-2 rounded-xl border border-slate-800/80">
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider pl-1">Project:</span>
            <select
              value={activeProjectId}
              onChange={(e) => selectProject(e.target.value)}
              className="bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all cursor-pointer font-medium"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3 bg-slate-900/60 p-2 rounded-xl border border-slate-800/80">
            {saveStatus === 'saving' ? (
              <span className="text-xs text-indigo-400 flex items-center gap-1.5 font-medium px-2">
                <Spinner size="sm" /> Saving...
              </span>
            ) : saveStatus === 'failed' ? (
              <span className="text-xs text-red-400 flex items-center gap-1.5 font-medium px-2">
                <span>⚠️</span> Save failed
              </span>
            ) : (
              <span className="text-xs text-emerald-400 flex items-center gap-1.5 font-medium px-2 font-mono">
                <span>✓</span> All changes saved
              </span>
            )}
            {saveStatus === 'failed' && (
              <Button
                variant="outline"
                size="sm"
                onClick={triggerSave}
                disabled={isSaving}
                className="text-xs border-red-500/30 hover:bg-red-500/10 text-red-400"
              >
                Retry Save
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsImportOpen(true)}
              className="text-xs text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/10"
            >
              📥 Import Schema
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ==================== LEFT PANEL: TABLES LIST ==================== */}
        <Card className="lg:col-span-3 p-4 flex flex-col gap-4 bg-slate-900/40 border-slate-800/80">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Tables ({totalTables})
            </h2>
            <Button
              variant="primary"
              size="sm"
              onClick={handleAddTable}
              className="py-1 px-2.5 text-xs"
            >
              ➕ Add Table
            </Button>
          </div>

          <div className="relative">
            <input
              type="text"
              placeholder="Search tables..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
            />
          </div>

          <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
            {filteredTables.length === 0 ? (
              <div className="text-xs text-slate-500 text-center py-6">
                No tables defined.
              </div>
            ) : (
              filteredTables.map((t) => (
                <div
                  key={t.id}
                  onClick={() => setSelectedTableId(t.id)}
                  className={`
                    w-full flex items-center justify-between p-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all border
                    ${
                      selectedTableId === t.id
                        ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                        : 'bg-slate-900/30 text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
                    }
                  `}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <span role="img" aria-hidden="true">
                      📊
                    </span>
                    <span className="truncate">{t.name}</span>
                    <span className="text-[10px] bg-slate-800 text-slate-400 py-0.5 px-1.5 rounded-full">
                      {t.columns.length}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRenameTable(t.id)
                      }}
                      className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-slate-200 cursor-pointer"
                      title="Rename Table"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteTable(t.id)
                      }}
                      className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-rose-400 cursor-pointer"
                      title="Delete Table"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* ==================== CENTER PANEL: SELECTED TABLE EDITOR & RELATIONSHIPS ==================== */}
        <div className="lg:col-span-6 space-y-6">
          <Card className="p-6 space-y-6 bg-slate-900/30 border-slate-800/80">
            {selectedTable ? (
              <>
                {/* Header Title Editor */}
                <div className="flex justify-between items-center pb-4 border-b border-slate-800/60">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-white tracking-tight">
                      {selectedTable.name}
                    </h2>
                    <button
                      onClick={() => handleRenameTable(selectedTable.id)}
                      className="text-xs text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      ✏️ Rename
                    </button>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleAddColumn(selectedTable.id)}
                  >
                    ➕ Add Column
                  </Button>
                </div>

                {/* Columns Table Editor */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800/60 text-slate-400 font-semibold uppercase tracking-wider">
                        <th className="py-2.5 pr-2">Column Name</th>
                        <th className="py-2.5 pr-2 w-28">Type</th>
                        <th className="py-2.5 pr-2 text-center w-14">PK</th>
                        <th className="py-2.5 pr-2 text-center w-14">Null</th>
                        <th className="py-2.5 pr-2 w-32">Default</th>
                        <th className="py-2.5 text-right w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40">
                      {selectedTable.columns.length === 0 ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="py-6 text-center text-slate-500"
                          >
                            No columns defined. Click "Add Column" to start.
                          </td>
                        </tr>
                      ) : (
                        selectedTable.columns.map((c) => (
                          <tr
                            key={c.id}
                            className="hover:bg-slate-900/20 group"
                          >
                            <td className="py-3 pr-2 font-medium text-slate-200">
                              <div className="flex items-center gap-2">
                                <span className="truncate">{c.name}</span>
                                <button
                                  onClick={() =>
                                    handleRenameColumn(
                                      selectedTable.id,
                                      c.id,
                                      c.name
                                    )
                                  }
                                  className="opacity-0 group-hover:opacity-100 text-[10px] text-indigo-400 hover:underline cursor-pointer"
                                >
                                  Edit
                                </button>
                              </div>
                            </td>
                            <td className="py-3 pr-2">
                              <select
                                value={c.type}
                                onChange={(e) =>
                                  handleUpdateColumn(selectedTable.id, c.id, {
                                    type: e.target.value,
                                  })
                                }
                                className="bg-slate-950 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                              >
                                <option value="INTEGER">INTEGER</option>
                                <option value="VARCHAR">VARCHAR</option>
                                <option value="TEXT">TEXT</option>
                                <option value="FLOAT">FLOAT</option>
                                <option value="BOOLEAN">BOOLEAN</option>
                                <option value="TIMESTAMP">TIMESTAMP</option>
                              </select>
                            </td>
                            <td className="py-3 pr-2 text-center">
                              <input
                                type="checkbox"
                                checked={c.isPrimaryKey}
                                onChange={(e) =>
                                  handleUpdateColumn(selectedTable.id, c.id, {
                                    isPrimaryKey: e.target.checked,
                                  })
                                }
                                className="rounded border-slate-800 bg-slate-950 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                                title="Primary Key"
                              />
                            </td>
                            <td className="py-3 pr-2 text-center">
                              <input
                                type="checkbox"
                                checked={c.isNullable}
                                disabled={c.isPrimaryKey}
                                onChange={(e) =>
                                  handleUpdateColumn(selectedTable.id, c.id, {
                                    isNullable: e.target.checked,
                                  })
                                }
                                className="rounded border-slate-800 bg-slate-950 text-indigo-600 focus:ring-indigo-500 cursor-pointer disabled:opacity-40"
                                title="Nullable"
                              />
                            </td>
                            <td className="py-3 pr-2">
                              <input
                                type="text"
                                value={c.defaultValue}
                                placeholder="NULL"
                                onChange={(e) =>
                                  handleUpdateColumn(selectedTable.id, c.id, {
                                    defaultValue: e.target.value,
                                  })
                                }
                                className="bg-slate-950 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                              />
                            </td>
                            <td className="py-3 text-right">
                              <button
                                onClick={() =>
                                  handleDeleteColumn(selectedTable.id, c.id)
                                }
                                className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-rose-400 cursor-pointer"
                                title="Delete Column"
                              >
                                🗑️
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <EmptyState
                title="No Table Selected"
                description="Select a table from the left pane or click 'Add Table' to begin editing fields."
                actionLabel="Add Table"
                onAction={handleAddTable}
              />
            )}
          </Card>

          {/* ==================== RELATIONSHIPS DESIGNER ==================== */}
          <Card className="p-6 space-y-6 bg-slate-900/30 border-slate-800/80">
            <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
              <span>🔗</span> Relationship Designer
            </h2>
            <Divider />

            {/* Relationship Creation Form */}
            {tables.length >= 2 ? (
              <div className="space-y-4 bg-slate-950/40 p-4 border border-slate-800/60 rounded-xl">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Source configuration */}
                  <div className="space-y-2">
                    <label className="text-[10px] uppercase font-bold text-slate-500">
                      Source Field (Foreign Key)
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={newRelSourceTable}
                        onChange={(e) => setNewRelSourceTable(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-1/2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        {tables.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={newRelSourceCol}
                        onChange={(e) => setNewRelSourceCol(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-1/2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        {(
                          tables.find((t) => t.id === newRelSourceTable)
                            ?.columns || []
                        ).map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Target configuration */}
                  <div className="space-y-2">
                    <label className="text-[10px] uppercase font-bold text-slate-500">
                      Target Field (References PK)
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={newRelTargetTable}
                        onChange={(e) => setNewRelTargetTable(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-1/2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        {tables.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={newRelTargetCol}
                        onChange={(e) => setNewRelTargetCol(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-1/2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        {(
                          tables.find((t) => t.id === newRelTargetTable)
                            ?.columns || []
                        ).map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                  <div className="space-y-2">
                    <label className="text-[10px] uppercase font-bold text-slate-500">
                      Relationship Name
                    </label>
                    <input
                      type="text"
                      value={newRelName}
                      onChange={(e) => setNewRelName(e.target.value)}
                      className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] uppercase font-bold text-slate-500">
                      Relationship Type
                    </label>
                    <select
                      value={newRelType}
                      onChange={(e) =>
                        setNewRelType(e.target.value as any)
                      }
                      className="bg-slate-900 border border-slate-800 rounded-lg py-1 px-2 text-xs text-slate-300 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="one-to-one">One-to-One</option>
                      <option value="one-to-many">One-to-Many</option>
                      <option value="many-to-one">Many-to-One</option>
                      <option value="many-to-many">Many-to-Many (Placeholder)</option>
                    </select>
                  </div>

                  <Button
                    variant="primary"
                    onClick={handleCreateRelationship}
                    className="w-full text-xs py-1.5"
                  >
                    Add Relationship
                  </Button>
                </div>

                {/* Additional Settings Toggles */}
                <div className="flex flex-wrap gap-4 pt-2">
                  <label className="flex items-center gap-2 text-xs text-slate-400">
                    <input
                      type="checkbox"
                      checked={newRelIsRequired}
                      onChange={(e) => setNewRelIsRequired(e.target.checked)}
                      className="rounded border-slate-800 bg-slate-950 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    />
                    <span>Required (NOT NULL)</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs text-slate-500 cursor-not-allowed" title="Cascade actions belong to Phase 16">
                    <input
                      type="checkbox"
                      disabled
                      checked
                      className="rounded border-slate-800 bg-slate-950 text-indigo-600 cursor-not-allowed opacity-50"
                    />
                    <span>Cascade Delete (Placeholder)</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs text-slate-500 cursor-not-allowed" title="Cascade actions belong to Phase 16">
                    <input
                      type="checkbox"
                      disabled
                      checked
                      className="rounded border-slate-800 bg-slate-950 text-indigo-600 cursor-not-allowed opacity-50"
                    />
                    <span>Cascade Update (Placeholder)</span>
                  </label>
                </div>
              </div>
            ) : (
              <Alert variant="info" title="Relational Design Constraint">
                Please add at least two tables on the Left Panel to establish relationship links.
              </Alert>
            )}

            {/* Relationships List */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-200">
                Configured Relationships ({totalRelationships})
              </h3>
              {relationships.length === 0 ? (
                <div className="text-xs text-slate-500 text-center py-6 border border-dashed border-slate-800 rounded-xl">
                  No relationships configured. Use the form above to add one.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {relationships.map((r) => {
                    const sTable = tables.find((t) => t.id === r.sourceTableId);
                    const tTable = tables.find((t) => t.id === r.targetTableId);
                    const sCol = sTable?.columns.find((c) => c.id === r.sourceColumnId);
                    const tCol = tTable?.columns.find((c) => c.id === r.targetColumnId);

                    return (
                      <div
                        key={r.id}
                        className="flex items-center justify-between p-3 bg-slate-950/20 border border-slate-800/80 rounded-xl text-xs hover:border-slate-700/60 transition-colors"
                      >
                        <div className="space-y-1 overflow-hidden pr-2">
                          <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                            <span>{r.name}</span>
                            {r.isRequired && (
                              <span className="text-[9px] bg-indigo-600/10 text-indigo-300 py-0.5 px-1.5 rounded-full border border-indigo-500/20 font-bold">
                                Required
                              </span>
                            )}
                          </div>
                          <div className="text-slate-400 flex items-center gap-2 flex-wrap">
                            <span className="text-slate-200 font-medium">
                              {sTable ? sTable.name : 'UnknownTable'}
                              .{sCol ? sCol.name : 'UnknownCol'}
                            </span>
                            <span className="text-[10px] bg-slate-800 text-slate-400 py-0.5 px-2 rounded-full border border-slate-700/60 font-semibold lowercase">
                              {r.type}
                            </span>
                            <span>───&gt;</span>
                            <span className="text-slate-200 font-medium">
                              {tTable ? tTable.name : 'UnknownTable'}
                              .{tCol ? tCol.name : 'UnknownCol'}
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteRelationship(r.id)}
                          className="p-1.5 hover:bg-slate-800 rounded text-slate-500 hover:text-rose-400 cursor-pointer shrink-0"
                          title="Delete Relationship"
                        >
                          🗑️
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* ==================== RIGHT PANEL: SCHEMA SUMMARY & DIAGNOSTICS ==================== */}
        <div className="lg:col-span-3 space-y-6">
          {/* AI Schema Assistant Panel */}
          <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
            <div className="flex justify-between items-center pb-2 border-b border-slate-800/60">
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <span>🤖</span> AI Assistant
              </h2>
              {aiStatus === 'completed' && (
                <span className="text-[10px] text-slate-500 italic">
                  ({aiExecutionTime.toFixed(0)}ms)
                </span>
              )}
            </div>

            {/* AI Assistant Status Cases */}
            {aiStatus === 'waiting' && (
              <div className="space-y-4 py-2">
                <div className="text-xs text-slate-400 leading-relaxed text-center">
                  Analyze your schema layout, table relationships, and naming standards to get design improvements.
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleAIAnalysis}
                  className="w-full flex items-center justify-center gap-1.5 py-2 text-xs"
                >
                  <span>🧠</span> Run AI Analysis
                </Button>
              </div>
            )}

            {aiStatus === 'analyzing' && (
              <div className="flex flex-col items-center justify-center py-8 gap-3">
                <Spinner size="md" />
                <span className="text-xs text-indigo-400 font-medium animate-pulse">
                  Analyzing schema design...
                </span>
              </div>
            )}

            {aiStatus === 'failed' && (
              <div className="space-y-4 py-2">
                <Alert variant="error" title="Analysis Failed">
                  {aiErrorMessage}
                </Alert>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAIAnalysis}
                  className="w-full text-xs"
                >
                  🔄 Retry Analysis
                </Button>
              </div>
            )}

            {aiStatus === 'completed' && (
              <div className="space-y-4">
                {/* Summary Text */}
                <div className="text-xs text-slate-300 bg-slate-950/40 p-3 rounded-xl border border-slate-800/60 leading-relaxed">
                  {aiSummary}
                </div>

                {/* Categories Filter list */}
                <div className="flex flex-wrap gap-1 border-b border-slate-800/40 pb-2">
                  {['All', 'Naming', 'Relationships', 'Performance', 'Validation', 'Best Practices'].map((cat) => {
                    const count = cat === 'All' 
                      ? aiSuggestions.filter(s => !dismissedSuggestions.includes(s.id) && !ignoredSuggestions.includes(s.id)).length
                      : aiSuggestions.filter(s => s.category === cat && !dismissedSuggestions.includes(s.id) && !ignoredSuggestions.includes(s.id)).length;
                    
                    return (
                      <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={`text-[10px] px-2 py-1 rounded-lg transition-all cursor-pointer font-medium
                          ${selectedCategory === cat
                            ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                            : 'bg-slate-950/40 text-slate-400 border border-transparent hover:text-slate-200'
                          }
                        `}
                      >
                        {cat} ({count})
                      </button>
                    );
                  })}
                </div>

                {/* Suggestions list */}
                <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                  {aiSuggestions
                    .filter((s) => {
                      if (dismissedSuggestions.includes(s.id)) return false;
                      if (ignoredSuggestions.includes(s.id)) return false;
                      if (selectedCategory !== 'All' && s.category !== selectedCategory) return false;
                      return true;
                    })
                    .length === 0 ? (
                      <div className="text-xs text-slate-500 text-center py-6">
                        No active suggestions in this category.
                      </div>
                    ) : (
                      aiSuggestions
                        .filter((s) => {
                          if (dismissedSuggestions.includes(s.id)) return false;
                          if (ignoredSuggestions.includes(s.id)) return false;
                          if (selectedCategory !== 'All' && s.category !== selectedCategory) return false;
                          return true;
                        })
                        .map((s) => {
                          const isAccepted = acceptedSuggestions.includes(s.id);
                          
                          // Badge color based on severity
                          let severityBadge = (
                            <span className="text-[9px] bg-slate-800 text-slate-400 py-0.5 px-2 rounded-full border border-slate-700/60 font-semibold uppercase">
                              {s.severity}
                            </span>
                          );
                          if (s.severity === 'high') {
                            severityBadge = (
                              <span className="text-[9px] bg-rose-950/30 text-rose-400 py-0.5 px-2 rounded-full border border-rose-500/20 font-bold uppercase">
                                High
                              </span>
                            );
                          } else if (s.severity === 'medium') {
                            severityBadge = (
                              <span className="text-[9px] bg-amber-950/30 text-amber-400 py-0.5 px-2 rounded-full border border-amber-500/20 font-bold uppercase">
                                Medium
                              </span>
                            );
                          } else if (s.severity === 'low') {
                            severityBadge = (
                              <span className="text-[9px] bg-blue-950/30 text-blue-400 py-0.5 px-2 rounded-full border border-blue-500/20 font-bold uppercase">
                                Low
                              </span>
                            );
                          }

                          return (
                            <div
                              key={s.id}
                              className={`p-3 rounded-xl border transition-all text-xs space-y-2.5
                                ${isAccepted 
                                  ? 'bg-emerald-950/10 border-emerald-500/20 opacity-90'
                                  : 'bg-slate-950/30 border-slate-850/80 hover:border-slate-800'
                                }
                              `}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-slate-200 truncate" title={s.title}>
                                  {s.title}
                                </span>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <span className="text-[9px] bg-slate-800/80 text-slate-400 py-0.5 px-1.5 rounded-md font-medium">
                                    {s.category}
                                  </span>
                                  {severityBadge}
                                </div>
                              </div>

                              <p className="text-slate-400 leading-relaxed text-[11px]">
                                {s.explanation}
                              </p>

                              {s.suggestedAction && (
                                <div className="p-2 bg-slate-950/50 rounded-lg border border-slate-850 border-dashed text-slate-300 text-[10px] leading-relaxed">
                                  <span className="font-medium text-indigo-400">💡 Suggestion:</span> {s.suggestedAction}
                                </div>
                              )}

                              {/* Interaction Action Buttons */}
                              {isAccepted ? (
                                <div className="text-[10px] text-emerald-400/90 font-medium bg-emerald-950/20 border border-emerald-500/10 p-1.5 rounded-lg text-center">
                                  ✓ Recommendation Accepted (Apply Manually)
                                </div>
                              ) : (
                                <div className="flex items-center gap-1.5 pt-1">
                                  <button
                                    onClick={() => handleAcceptSuggestion(s.id)}
                                    className="flex-1 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-300 border border-indigo-500/20 hover:border-indigo-500/40 rounded-lg py-1 px-2 transition-all cursor-pointer font-medium text-[10px] text-center"
                                  >
                                    Accept
                                  </button>
                                  <button
                                    onClick={() => handleDismissSuggestion(s.id)}
                                    className="bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-slate-200 border border-transparent rounded-lg py-1 px-2 transition-all cursor-pointer text-[10px] text-center"
                                    title="Dismiss this suggestion for this run"
                                  >
                                    Dismiss
                                  </button>
                                  <button
                                    onClick={() => handleIgnoreSuggestion(s.id)}
                                    className="bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-slate-200 border border-transparent rounded-lg py-1 px-2 transition-all cursor-pointer text-[10px] text-center"
                                    title="Ignore permanently (session only)"
                                  >
                                    Ignore
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })
                    )}
                </div>

                <Divider />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAIAnalysis}
                  className="w-full text-xs py-1.5"
                >
                  🔄 Re-run Analysis
                </Button>
              </div>
            )}
          </Card>

          {/* Schema Summary Statistics */}
          <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Schema Summary
            </h2>
            <Divider />
            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Total Tables</span>
                <span className="font-semibold text-slate-200">
                  {totalTables}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Columns</span>
                <span className="font-semibold text-slate-200">
                  {totalColumns}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Primary Keys</span>
                <span className="font-semibold text-slate-200">
                  {totalPrimaryKeys}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Relationships</span>
                <span className="font-semibold text-slate-200">
                  {totalRelationships}
                </span>
              </div>
            </div>

            <Divider label="Relationship Types" />
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">One-to-One</span>
                <span className="font-semibold text-slate-200">{oneToOneCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">One-to-Many</span>
                <span className="font-semibold text-slate-200">{oneToManyCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Many-to-One</span>
                <span className="font-semibold text-slate-200">{manyToOneCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Many-to-Many</span>
                <span className="font-semibold text-slate-200">{manyToManyCount}</span>
              </div>
            </div>

            <Divider label="Designer Insights" />
            <div className="space-y-2 text-xs">
              <div className="flex flex-col gap-1">
                <span className="text-slate-400">Tables Without Links ({tablesWithoutRelationships.length})</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {tablesWithoutRelationships.length === 0 ? (
                    <span className="text-[10px] text-slate-500 italic">None</span>
                  ) : (
                    tablesWithoutRelationships.map((t) => (
                      <span key={t.id} className="text-[9px] bg-slate-800 text-slate-400 py-0.5 px-1.5 rounded-full border border-slate-700/60">
                        {t.name}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Validation & Warnings */}
          <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Validation & Warnings ({allWarnings.length})
            </h2>
            <Divider />
            {allWarnings.length > 0 ? (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {allWarnings.map((warning, idx) => (
                  <Alert key={idx} variant="warning" title="Design Warning">
                    {warning}
                  </Alert>
                ))}
              </div>
            ) : totalTables > 0 ? (
              <Alert variant="success" title="Validation Status">
                No structural warnings detected. Schema and relations match basic database validation criteria.
              </Alert>
            ) : (
              <div className="text-xs text-slate-500 text-center py-2">
                Create tables to run diagnostic checks.
              </div>
            )}
            <Divider />
            <div className="text-[10px] text-slate-500 leading-relaxed">
              Multi-agent semantic validation runner will be integrated in Phase
              15.
            </div>
          </Card>
        </div>
      </div>

      {/* ==================== IMPORT SCHEMA MODAL ==================== */}
      {isImportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm text-left">
          <Card className="w-full max-w-2xl bg-slate-900 border-slate-800 flex flex-col max-h-[95vh] overflow-hidden animate-fade-in">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-800">
              <h3 className="text-base font-bold text-slate-200 flex items-center gap-2">
                <span>📥</span> Import Database Schema
              </h3>
              <button
                onClick={() => setIsImportOpen(false)}
                className="text-slate-400 hover:text-slate-200 text-lg focus:outline-none"
              >
                ✕
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-5 overflow-y-auto flex-1 text-xs text-slate-350">
              {importError && (
                <Alert variant="error" title="Import Failed">
                  {importError}
                </Alert>
              )}

              {/* Drag and Drop Area */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Drag & Drop File Upload
                </label>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer ${
                    isDragging
                      ? 'border-indigo-500 bg-indigo-500/5'
                      : importFile
                        ? 'border-emerald-500/50 bg-emerald-500/5'
                        : 'border-slate-800 hover:border-slate-700 bg-slate-950/40'
                  }`}
                >
                  <input
                    type="file"
                    id="schema-file-upload"
                    accept=".sql,.ddl,.csv,.xlsx,.json,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <label htmlFor="schema-file-upload" className="cursor-pointer space-y-2 block">
                    <span className="text-3xl block">
                      {importFile ? '📄' : '📁'}
                    </span>
                    <span className="block font-medium text-slate-300">
                      {importFile ? (
                        <span className="text-emerald-400 font-bold">{importFile.name}</span>
                      ) : (
                        'Drag your schema file here or click to browse'
                      )}
                    </span>
                    <span className="block text-[10px] text-slate-500">
                      Supports *.sql, *.ddl, *.csv, *.xlsx, *.json, *.txt
                    </span>
                  </label>
                </div>
              </div>

              {/* File Type Selector */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Format / File Type
                  </label>
                  <select
                    value={importFileType}
                    onChange={(e) => setImportFileType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg p-2 text-slate-200 focus:outline-none"
                  >
                    <option value="sql">SQL / DDL Query</option>
                    <option value="json">JSON Document</option>
                    <option value="csv">CSV (Comma-Separated)</option>
                    <option value="xlsx">Excel Workbook</option>
                    <option value="txt">Text File (Plain)</option>
                  </select>
                </div>
                {importFile && (
                  <div className="flex items-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setImportFile(null)}
                      className="w-full text-slate-400 border-slate-850 hover:bg-slate-800"
                    >
                      Clear Uploaded File
                    </Button>
                  </div>
                )}
              </div>

              {/* SQL Text Area (Paste SQL) */}
              {!importFile && (
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Or Paste SQL / DDL / JSON Raw Code
                  </label>
                  <textarea
                    rows={8}
                    value={importText}
                    onChange={(e) => setImportText(e.target.value)}
                    placeholder="CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(100));"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 font-mono text-[11px] text-slate-350 placeholder:text-slate-650 focus:outline-none"
                  />
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-3 p-5 border-t border-slate-800 bg-slate-900/60">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsImportOpen(false)}
                disabled={isImporting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleImportSchema}
                disabled={isImporting || (!importFile && !importText.trim())}
                className="gap-2"
              >
                {isImporting ? (
                  <>
                    <Spinner size="sm" /> Importing...
                  </>
                ) : (
                  'Import Schema'
                )}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
