import { useState } from 'react'
import {
  Button,
  Card,
  Alert,
  Divider,
  PageHeader,
  EmptyState,
} from '../../components/ui'

interface Column {
  id: string
  name: string
  type: string
  isPrimaryKey: boolean
  isNullable: boolean
  defaultValue: string
}

interface Table {
  id: string
  name: string
  columns: Column[]
}

export const SchemaGenerator = () => {
  const [tables, setTables] = useState<Table[]>([
    {
      id: '1',
      name: 'users',
      columns: [
        {
          id: 'c1',
          name: 'id',
          type: 'INTEGER',
          isPrimaryKey: true,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'c2',
          name: 'email',
          type: 'VARCHAR',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'c3',
          name: 'created_at',
          type: 'TIMESTAMP',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: 'CURRENT_TIMESTAMP',
        },
      ],
    },
    {
      id: '2',
      name: 'orders',
      columns: [
        {
          id: 'o1',
          name: 'id',
          type: 'INTEGER',
          isPrimaryKey: true,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'o2',
          name: 'user_id',
          type: 'INTEGER',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'o3',
          name: 'total',
          type: 'FLOAT',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '0.00',
        },
        {
          id: 'o4',
          name: 'status',
          type: 'VARCHAR',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: "'pending'",
        },
      ],
    },
  ])

  const [selectedTableId, setSelectedTableId] = useState<string>('1')
  const [tableSearch, setTableSearch] = useState<string>('')

  const selectedTable = tables.find((t) => t.id === selectedTableId)

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
  }

  // Stats
  const totalTables = tables.length
  const totalColumns = tables.reduce((acc, t) => acc + t.columns.length, 0)
  const totalPrimaryKeys = tables.reduce(
    (acc, t) => acc + t.columns.filter((c) => c.isPrimaryKey).length,
    0
  )
  const estimatedRelationships = Math.max(0, totalTables - 1)

  const filteredTables = tables.filter((t) =>
    t.name.toLowerCase().includes(tableSearch.toLowerCase())
  )

  const validationWarnings = tables.reduce<string[]>((acc, t) => {
    const hasPk = t.columns.some((c) => c.isPrimaryKey)
    if (!hasPk) {
      acc.push(`Table "${t.name}" has no primary key defined.`)
    }
    if (t.columns.length === 0) {
      acc.push(`Table "${t.name}" has no columns defined.`)
    }
    return acc
  }, [])

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left">
      <PageHeader
        title="Schema Designer"
        subtitle="Interactively build entity relationship tables and columns for database generation."
      />

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

        {/* ==================== CENTER PANEL: SELECTED TABLE EDITOR ==================== */}
        <Card className="lg:col-span-6 p-6 space-y-6 bg-slate-900/30 border-slate-800/80">
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
                        <tr key={c.id} className="hover:bg-slate-900/20 group">
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

              {/* Relationship Section Placeholder */}
              <div className="pt-6 border-t border-slate-800/60 space-y-3">
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <span>🔗</span> Relationships Section
                </h3>
                <Alert variant="info" title="Relationship Configurator">
                  Cross-table constraints and foreign keys will be configurable
                  in Phase 14 (Relationship Editor).
                </Alert>
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

        {/* ==================== RIGHT PANEL: SCHEMA SUMMARY & DIAGNOSTICS ==================== */}
        <div className="lg:col-span-3 space-y-6">
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
                <span className="text-slate-400">Est. Relationships</span>
                <span className="font-semibold text-slate-200">
                  {estimatedRelationships}
                </span>
              </div>
            </div>
          </Card>

          {/* Validation & Warnings Placeholder */}
          <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Validation & Warnings
            </h2>
            <Divider />
            {validationWarnings.length > 0 ? (
              <div className="space-y-2">
                {validationWarnings.map((warning, idx) => (
                  <Alert key={idx} variant="warning" title="Design Warning">
                    {warning}
                  </Alert>
                ))}
              </div>
            ) : totalTables > 0 ? (
              <Alert variant="success" title="Validation Status">
                No structural warnings detected. Schema matches basic
                conventions.
              </Alert>
            ) : (
              <div className="text-xs text-slate-500 text-center py-2">
                Create a table to run diagnostic checks.
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
    </div>
  )
}
