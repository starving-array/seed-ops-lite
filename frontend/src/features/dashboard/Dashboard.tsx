import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Badge, Divider, Grid } from '../../components/ui'
import { useAppInfo } from '../../context/AppContext'
import { healthService } from '../../services/health'

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
