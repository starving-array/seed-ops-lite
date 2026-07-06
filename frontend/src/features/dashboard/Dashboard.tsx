import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Badge, Divider, Grid } from '../../components/ui'
import { useAppInfo } from '../../context/AppContext'
import { healthService } from '../../services/health'
import { schemaService } from '../../services/schema'
import { StatusDiagnosticsCard } from './StatusDiagnosticsCard'

export const Dashboard = () => {
  const navigate = useNavigate()
  const { version, env } = useAppInfo()
  const [healthStatus, setHealthStatus] = useState<
    'Checking' | 'Healthy' | 'Offline'
  >('Checking')

  const [stats, setStats] = useState<{
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
  } | null>(null)

  useEffect(() => {
    healthService.checkStatus().then((res) => {
      setHealthStatus(res.success ? 'Healthy' : 'Offline')
    })
    schemaService.getStats().then((res) => {
      if (res.success && res.data) {
        setStats(res.data)
      }
    })
  }, [])

  const metrics = [
    { 
      label: 'Total Projects', 
      value: stats?.projects_count !== undefined ? String(stats.projects_count) : '...', 
      change: 'Active workspaces', 
      icon: '📁' 
    },
    {
      label: 'Schemas Verified',
      value: stats?.schemas_count !== undefined ? String(stats.schemas_count) : '...',
      change: `${stats?.validation_statistics.passed ?? 0} passed / ${stats?.validation_statistics.total_runs ?? 0} runs`,
      icon: '🛡️',
    },
    {
      label: 'Synthetic Rows Generated',
      value: stats?.total_generated_rows !== undefined ? stats.total_generated_rows.toLocaleString() : '...',
      change: `across ${stats?.jobs_count ?? 0} jobs`,
      icon: '⚙️',
    },
    {
      label: 'Export Templates',
      value: stats?.exports_count !== undefined ? String(stats.exports_count) : '...',
      change: 'Formats: SQL, CSV, JSON',
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
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 text-left animate-fade-in font-sans">
      {/* Welcome Section */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900/60 to-slate-900/40 border border-slate-800/80 rounded-2xl p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
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

        {/* Connection & Diagnostics Sidebar */}
        <div className="space-y-6">
          <StatusDiagnosticsCard />
          
          {/* Token Usage Diagnostics Card */}
          <Card className="p-6 space-y-4 border border-slate-800 bg-slate-900/40">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <span>🤖</span> LLM Token Diagnostics
            </h2>
            <Divider />
            <div className="space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Active Provider</span>
                <span className="text-indigo-300 font-semibold">
                  {stats?.token_usage.active_provider ?? 'Google Gemini'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Active Model</span>
                <span className="text-indigo-300 font-semibold font-mono">
                  {stats?.token_usage.active_model ?? 'gemini-1.5-flash'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Tokens</span>
                <span className="text-slate-200 font-bold font-mono">
                  {stats?.token_usage.total_tokens.toLocaleString() ?? '142,500'}
                </span>
              </div>
              <div className="pl-3 space-y-1.5 border-l border-slate-800">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-500">Input Tokens</span>
                  <span className="text-slate-400 font-mono">
                    {stats?.token_usage.input_tokens.toLocaleString() ?? '82,100'}
                  </span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-500">Output Tokens</span>
                  <span className="text-slate-400 font-mono">
                    {stats?.token_usage.output_tokens.toLocaleString() ?? '60,400'}
                  </span>
                </div>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Tokens per Job (avg)</span>
                <span className="text-slate-300 font-mono">
                  {stats?.token_usage.tokens_per_job.toLocaleString() ?? '1,250'}
                </span>
              </div>
              <div className="flex justify-between border-t border-slate-800/60 pt-2 mt-2">
                <span className="text-slate-400 font-semibold">Estimated Cost (USD)</span>
                <span className="text-emerald-400 font-bold font-mono">
                  ${stats?.token_usage.estimated_cost_usd ?? '0.0125'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </Grid>
    </div>
  )
}
