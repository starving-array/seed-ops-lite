import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Badge,
  Alert,
  Divider,
  Stack,
  Grid,
  PageHeader,
  Spinner,
  EmptyState,
} from './components/ui'
import { useAppInfo } from './context/AppContext'
import { healthService } from './services/health'

interface PageProps {
  title: string
  description: string
}

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

const PagePlaceholder = ({ title, description }: PageProps) => {
  return (
    <div className="p-6 md:p-10 max-w-4xl">
      <div className="px-4 py-1 text-xs font-semibold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-md inline-block mb-4">
        Placeholder Page
      </div>
      <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-3">
        {title}
      </h1>
      <p className="text-slate-400 text-base leading-relaxed">
        {description}
      </p>
    </div>
  )
}

export const Dashboard = () => {
  const navigate = useNavigate()
  const { version, env } = useAppInfo()
  const [healthStatus, setHealthStatus] = useState<
    'Checking' | 'Healthy' | 'Offline'
  >('Checking')

  useEffect(() => {
    healthService.checkStatus().then((res) => {
      setHealthStatus(res.success ? 'Healthy' : 'Offline')
    })
  }, [])

  const metrics = [
    { label: 'Total Projects', value: '3', change: '+1 this week', icon: '📁' },
    {
      label: 'Schemas Verified',
      value: '18',
      change: '100% success rate',
      icon: '🛡️',
    },
    {
      label: 'Synthetic Rows Generated',
      value: '1.2M',
      change: '+240K today',
      icon: '⚙️',
    },
    {
      label: 'Export Templates',
      value: '5',
      change: 'SQL, CSV, JSON',
      icon: '📥',
    },
  ]

  const quickActions = [
    {
      label: 'New Project',
      path: '/projects',
      icon: '📁',
      variant: 'primary' as const,
    },
    {
      label: 'Generate Schema',
      path: '/schema-generator',
      icon: '🛠️',
      variant: 'outline' as const,
    },
    {
      label: 'Validate Schema',
      path: '/schema-validation',
      icon: '🛡️',
      variant: 'outline' as const,
    },
    {
      label: 'Generate Data',
      path: '/data-generation',
      icon: '⚙️',
      variant: 'outline' as const,
    },
    {
      label: 'Export Dataset',
      path: '/export',
      icon: '📥',
      variant: 'outline' as const,
    },
  ]

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 text-left">
      {/* Welcome Section */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900/60 to-slate-900/40 border border-slate-800/80 rounded-2xl p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 animate-fade-in">
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Welcome to SafeSeed-Ops 🌱
          </h1>
          <p className="text-slate-400 text-sm md:text-base max-w-xl">
            Configure entity relational schemas, validate constraints with
            multi-agent checks, and generate synthetic seed data instantly.
          </p>
        </div>
        <div className="flex flex-col gap-1 text-xs text-slate-500 md:text-right">
          <div>
            Version:{' '}
            <span className="font-semibold text-slate-300">{version}</span>
          </div>
          <div>
            Environment:{' '}
            <span className="font-semibold text-slate-300 capitalize">
              {env}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1 md:justify-end">
            <span>API Health:</span>
            <Badge
              variant={
                healthStatus === 'Healthy'
                  ? 'success'
                  : healthStatus === 'Offline'
                    ? 'error'
                    : 'info'
              }
            >
              {healthStatus}
            </Badge>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <Grid cols={4} className="gap-6">
        {metrics.map((metric, idx) => (
          <Card
            key={idx}
            hoverable
            className="p-5 flex flex-col justify-between h-36"
          >
            <div className="flex items-start justify-between">
              <span className="text-2xl" role="img" aria-label={metric.label}>
                {metric.icon}
              </span>
              <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                {metric.change}
              </span>
            </div>
            <div className="mt-4">
              <div className="text-2xl font-bold text-white tracking-tight">
                {metric.value}
              </div>
              <div className="text-xs text-slate-400 mt-1">{metric.label}</div>
            </div>
          </Card>
        ))}
      </Grid>

      {/* Quick Actions & Connection Diagnostics */}
      <Grid cols={3} className="gap-6">
        {/* Quick Actions Panel */}
        <Card className="col-span-1 md:col-span-2 p-6 space-y-4">
          <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            <span>⚡</span> Quick Actions
          </h2>
          <Divider />
          <div className="flex flex-wrap gap-3">
            {quickActions.map((action, idx) => (
              <Button
                key={idx}
                variant={action.variant}
                onClick={() => navigate(action.path)}
                className="flex items-center gap-2"
              >
                <span>{action.icon}</span>
                <span>{action.label}</span>
              </Button>
            ))}
          </div>
        </Card>

        {/* Connection Diagnostics Panel */}
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            <span>🏥</span> Status Diagnostics
          </h2>
          <Divider />
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">FastAPI status</span>
              <span className="font-semibold text-slate-200">Online</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">SQLite backend</span>
              <span className="font-semibold text-slate-200">Connected</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Merge conflicts</span>
              <span className="font-semibold text-slate-200 text-emerald-400">
                None
              </span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Git quality gates</span>
              <span className="font-semibold text-slate-200 text-emerald-400">
                Passed
              </span>
            </div>
          </div>
        </Card>
      </Grid>
    </div>
  )
}

export const Projects = () => {
  const [projects, setProjects] = useState([
    {
      id: '1',
      name: 'SafeSeed Core DB',
      description:
        'Core schema configuration storing transaction records and customer profiles.',
      tables: 8,
      status: 'verified',
      updatedAt: '2026-06-27',
    },
    {
      id: '2',
      name: 'Analytics Warehouse',
      description:
        'OLAP schema targeting customer telemetry, clicks, and page view actions.',
      tables: 12,
      status: 'pending',
      updatedAt: '2026-06-25',
    },
  ])

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  const handleCreateProject = () => {
    const name = prompt('Enter Project Name:')
    if (!name) return
    const description =
      prompt('Enter Project Description:') || 'No description provided.'
    const newProj = {
      id: Math.random().toString(36).substring(2, 9),
      name,
      description,
      tables: 0,
      status: 'pending',
      updatedAt: new Date().toISOString().split('T')[0],
    }
    setProjects((prev) => [newProj, ...prev])
  }

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || p.status === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 text-left">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          title="Project Workspace"
          subtitle="Manage, edit, and orchestrate synthetic schema seeding models."
        />
        <Button
          variant="primary"
          onClick={handleCreateProject}
          className="self-start sm:self-auto flex items-center gap-2"
        >
          <span>➕</span> New Project
        </Button>
      </div>

      {/* Search & Filter Toolbar */}
      <Card className="p-4 flex flex-col md:flex-row gap-4 justify-between items-center bg-slate-900/60 border-slate-800/80">
        <div className="w-full md:w-72 relative">
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
          />
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'all'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('verified')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'verified'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            Verified
          </button>
          <button
            onClick={() => setFilter('pending')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'pending'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            Pending
          </button>
        </div>
      </Card>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <EmptyState
          title="No Projects Found"
          description="Could not find any projects matching your search. Create a new one to begin designing seeding schemas."
          actionLabel="Create Project"
          onAction={handleCreateProject}
        />
      ) : (
        <Grid cols={3} className="gap-6">
          {filteredProjects.map((p) => (
            <Card
              key={p.id}
              hoverable
              className="p-6 flex flex-col justify-between h-48 border border-slate-800/80 hover:border-slate-700/60 bg-slate-900/30"
            >
              <div className="space-y-2">
                <div className="flex justify-between items-start">
                  <h3 className="font-bold text-slate-200 text-base truncate pr-2">
                    {p.name}
                  </h3>
                  <Badge
                    variant={p.status === 'verified' ? 'success' : 'warning'}
                  >
                    {p.status}
                  </Badge>
                </div>
                <p className="text-slate-400 text-xs line-clamp-3">
                  {p.description}
                </p>
              </div>
              <div className="flex justify-between items-center pt-4 border-t border-slate-800/60 text-[10px] text-slate-500">
                <span>📊 {p.tables} tables</span>
                <span>Last updated: {p.updatedAt}</span>
              </div>
            </Card>
          ))}
        </Grid>
      )}
    </div>
  )
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

export const SchemaValidation = () => (
  <PagePlaceholder
    title="Schema Validation"
    description="Trigger multi-agent validation loops to ensure schema integrity and consistency checks."
  />
)

export const DataGeneration = () => (
  <PagePlaceholder
    title="Data Generation"
    description="Configure and execute parallel data generation runs with custom scaling constraints."
  />
)

export const Export = () => (
  <PagePlaceholder
    title="Export"
    description="Export generated datasets to target files including CSV, SQL inserts, or JSON formats."
  />
)

export const Observability = () => (
  <PagePlaceholder
    title="Observability"
    description="Real-time telemetry, structured application traces, system logs, and generation diagnostics."
  />
)

export const Settings = () => (
  <PagePlaceholder
    title="Settings"
    description="Configure global application properties, API access keys, connection pools, and agent models."
  />
)

export const About = () => {
  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto text-left space-y-8">
      <PageHeader
        title="About & Design System Showcase"
        subtitle="SafeSeed-Ops version 1.0.0-rc1. Reusable primitives and style conventions built with React and Tailwind CSS v4."
      />

      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-200">Button Variants</h2>
        <Stack direction="row" gap="sm">
          <Button variant="primary">Primary Button</Button>
          <Button variant="secondary">Secondary Button</Button>
          <Button variant="outline">Outline Button</Button>
          <Button variant="ghost">Ghost Button</Button>
          <Button variant="danger">Danger Button</Button>
        </Stack>
      </section>

      <Divider label="UI Primitives" />

      <Grid cols={2}>
        <Card hoverable className="space-y-4">
          <h3 className="text-base font-bold text-slate-200">System Badges</h3>
          <Stack direction="row" gap="sm">
            <Badge variant="info">Info</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="error">Error</Badge>
          </Stack>
        </Card>

        <Card hoverable className="flex items-center justify-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <Spinner size="sm" />
            <span className="text-xs text-slate-500">Small</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Spinner size="md" />
            <span className="text-xs text-slate-500">Medium</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Spinner size="lg" />
            <span className="text-xs text-slate-500">Large</span>
          </div>
        </Card>
      </Grid>

      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-200">Alert Messages</h2>
        <Stack gap="sm">
          <Alert variant="info" title="Information Update">
            All system connection endpoints are initialized and running in shell
            configuration mode.
          </Alert>
          <Alert variant="success" title="Quality Gate Verification">
            All backend and frontend package lint, formatting, and unit tests
            completed with zero errors.
          </Alert>
        </Stack>
      </section>
    </div>
  )
}

export const NotFound = () => (
  <PagePlaceholder
    title="404 Not Found"
    description="The page you are looking for does not exist or has been moved."
  />
)
