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

export const SchemaGenerator = () => (
  <PagePlaceholder
    title="Schema Generator"
    description="Design and configure relational entity schemas, column definitions, and seeding attributes."
  />
)

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
