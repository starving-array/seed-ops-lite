import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Card, Badge, Spinner, Button, Divider } from '../../components/ui'
import { healthService } from '../../services/health'
import type { HealthReport } from '../../services/health'

export type StatusType = 'healthy' | 'warning' | 'critical' | 'loading'

interface StatusIconProps {
  status: StatusType
}

export const StatusIcon = React.memo(({ status }: StatusIconProps) => {
  if (status === 'loading') {
    return <Spinner size="sm" className="text-indigo-400" />
  }

  if (status === 'healthy') {
    return (
      <svg
        className="w-5 h-5 text-emerald-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Healthy"
        role="img"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
    )
  }

  if (status === 'warning') {
    return (
      <svg
        className="w-5 h-5 text-amber-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Warning"
        role="img"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
    )
  }

  return (
    <svg
      className="w-5 h-5 text-red-500"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Critical"
      role="img"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
})

StatusIcon.displayName = 'StatusIcon'

interface StatusRowProps {
  label: string
  value: string
  status: StatusType
}

export const StatusRow = React.memo(({ label, value, status }: StatusRowProps) => {
  return (
    <div
      className="flex items-center justify-between py-2.5 border-b border-slate-800/40 last:border-0"
      role="status"
      aria-live="polite"
    >
      <span className="text-slate-400 text-sm font-medium">{label}</span>
      <div className="flex items-center gap-3">
        <span
          className={`text-sm font-semibold ${
            status === 'healthy'
              ? 'text-slate-200'
              : status === 'warning'
                ? 'text-amber-400'
                : status === 'critical'
                  ? 'text-red-400'
                  : 'text-slate-500'
          }`}
        >
          {value}
        </span>
        <StatusIcon status={status} />
      </div>
    </div>
  )
})

StatusRow.displayName = 'StatusRow'

export type OverallHealthType = 'Healthy' | 'Degraded' | 'Critical' | 'Checking'

interface HealthBadgeProps {
  status: OverallHealthType
}

export const HealthBadge = React.memo(({ status }: HealthBadgeProps) => {
  const variantMap: Record<OverallHealthType, 'info' | 'success' | 'warning' | 'error'> = {
    Checking: 'info',
    Healthy: 'success',
    Degraded: 'warning',
    Critical: 'error',
  }

  return (
    <Badge
      variant={variantMap[status]}
      className="text-xs font-bold px-3 py-1 animate-pulse-subtle"
    >
      {status}
    </Badge>
  )
})

HealthBadge.displayName = 'HealthBadge'

export interface RuntimeEvent {
  event: string
  timestamp: string
}

interface StatusDiagnosticsCardProps {
  mockData?: HealthReport | null
  mockLoading?: boolean
  mockOffline?: boolean
  onViewDetails?: () => void
  mockModalOpen?: boolean
  mockExpandedSections?: Record<string, boolean>
  mockEvents?: RuntimeEvent[]
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

interface CollapsibleSectionProps {
  title: string
  isOpen: boolean
  onToggle: () => void
  children: React.ReactNode
  icon?: string
}

const CollapsibleSection = ({ title, isOpen, onToggle, children, icon = '📁' }: CollapsibleSectionProps) => {
  return (
    <div className="border border-slate-800 rounded-xl bg-slate-950/30 overflow-hidden transition-all duration-200">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left font-semibold text-slate-200 hover:bg-slate-800/40 transition-colors focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2">
          <span role="img" aria-hidden="true">{icon}</span>
          <span>{title}</span>
        </span>
        <svg
          className={`w-5 h-5 text-slate-400 transform transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && <div className="p-4 border-t border-slate-800/60 bg-slate-900/40 space-y-1">{children}</div>}
    </div>
  )
}

export const StatusDiagnosticsCard = ({
  mockData = null,
  mockLoading = false,
  mockOffline = false,
  onViewDetails,
  mockModalOpen = false,
  mockExpandedSections = undefined,
  mockEvents = undefined,
}: StatusDiagnosticsCardProps) => {
  const [data, setData] = useState<HealthReport | null>(mockData)
  const [loading, setLoading] = useState<boolean>(
    mockLoading || (mockData === null && !mockOffline)
  )
  const [isOffline, setIsOffline] = useState<boolean>(mockOffline)
  const [isModalOpen, setIsModalOpen] = useState<boolean>(mockModalOpen)
  const [lastUpdated, setLastUpdated] = useState<string>('Never')
  const [responseTimeMs, setResponseTimeMs] = useState<number | null>(null)
  const [refreshing, setRefreshing] = useState<boolean>(false)
  const [copied, setCopied] = useState<boolean>(false)

  // Timeline state
  const [runtimeEvents, setRuntimeEvents] = useState<RuntimeEvent[]>(
    mockEvents || [
      { event: 'Application Started', timestamp: new Date().toISOString() },
    ]
  )
  const prevModeRef = useRef<string | null>(null)

  // Section expand state (remembered while modal is open)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(
    mockExpandedSections || {
      overall: true,
      app: false,
      runtime: false,
      persistence: false,
      ai: false,
      repo: false,
      perf: false,
      events: false,
    }
  )

  // Modal Focus Trap Refs
  const modalRef = useRef<HTMLDivElement>(null)
  const previousActiveElement = useRef<HTMLElement | null>(null)

  const fetchHealth = async (isManual = false) => {
    if (isManual) {
      setRefreshing(true)
    }
    const start = performance.now()
    try {
      const res = await healthService.checkStatus()
      const end = performance.now()
      if (res.success && res.data) {
        setData(res.data)
        setIsOffline(false)
        setResponseTimeMs(Math.round(end - start))
        setLastUpdated(new Date().toLocaleTimeString())
      } else {
        setIsOffline(true)
      }
    } catch {
      setIsOffline(true)
    } finally {
      if (isManual) {
        setRefreshing(false)
      } else {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    if (mockData || mockLoading || mockOffline) {
      setData(mockData)
      setLoading(mockLoading)
      setIsOffline(mockOffline)
      if (mockData) {
        setLastUpdated(new Date().toLocaleTimeString())
      }
      return
    }

    fetchHealth(false)

    const interval = setInterval(() => {
      fetchHealth(false)
    }, 10000)

    return () => {
      clearInterval(interval)
    }
  }, [mockData, mockLoading, mockOffline])

  // Track runtime events dynamically
  useEffect(() => {
    if (mockEvents || !data) return
    const currentMode = data.runtime_status?.mode
    const now = new Date().toISOString()
    
    if (prevModeRef.current !== null && prevModeRef.current !== currentMode) {
      const newEvents: RuntimeEvent[] = []
      if (currentMode === 'redis') {
        newEvents.push({ event: 'Redis Recovered', timestamp: now })
        newEvents.push({ event: 'Runtime Switched to Redis', timestamp: now })
      } else if (currentMode === 'memory') {
        newEvents.push({ event: 'Memory Fallback Activated', timestamp: now })
      }
      setRuntimeEvents((prev) => [...newEvents, ...prev].slice(0, 10))
    } else if (prevModeRef.current === null) {
      const initialEvents: RuntimeEvent[] = []
      if (currentMode === 'redis') {
        initialEvents.push({ event: 'Redis Connected', timestamp: now })
      } else if (currentMode === 'memory') {
        initialEvents.push({ event: 'Memory Fallback Activated', timestamp: now })
      }
      setRuntimeEvents((prev) => [...initialEvents, ...prev].slice(0, 10))
    }
    prevModeRef.current = currentMode
  }, [data, mockEvents])

  // Accessibility keyboard focus trap & escape key listener
  useEffect(() => {
    if (!isModalOpen) return

    previousActiveElement.current = document.activeElement as HTMLElement
    
    const focusableElementsSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    const getFocusable = () => {
      if (!modalRef.current) return []
      return Array.from(modalRef.current.querySelectorAll(focusableElementsSelector)) as HTMLElement[]
    }

    const focusables = getFocusable()
    if (focusables.length > 0) {
      focusables[0].focus()
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsModalOpen(false)
        return
      }

      if (e.key === 'Tab') {
        const list = getFocusable()
        if (list.length === 0) return

        const first = list[0]
        const last = list[list.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === first) {
            last.focus()
            e.preventDefault()
          }
        } else {
          if (document.activeElement === last) {
            first.focus()
            e.preventDefault()
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      if (previousActiveElement.current) {
        previousActiveElement.current.focus()
      }
    }
  }, [isModalOpen])

  // Compute states
  const states = useMemo(() => {
    if (loading) {
      return {
        overall: 'Checking' as OverallHealthType,
        fastapi: { value: 'Loading', status: 'loading' as StatusType },
        runtime: { value: 'Loading', status: 'loading' as StatusType },
        sqlite: { value: 'Loading', status: 'loading' as StatusType },
        redis: { value: 'Loading', status: 'loading' as StatusType },
        llm: { value: 'Loading', status: 'loading' as StatusType },
        qualityGates: { value: 'Loading', status: 'loading' as StatusType },
        runtimeState: 'Loading',
      }
    }

    if (isOffline) {
      return {
        overall: 'Critical' as OverallHealthType,
        fastapi: { value: 'Offline', status: 'critical' as StatusType },
        runtime: { value: 'Disconnected', status: 'critical' as StatusType },
        sqlite: { value: 'Disconnected', status: 'critical' as StatusType },
        redis: { value: 'Disconnected', status: 'critical' as StatusType },
        llm: { value: 'Unavailable', status: 'critical' as StatusType },
        qualityGates: { value: 'Failed', status: 'critical' as StatusType },
        runtimeState: 'Disconnected',
      }
    }

    const hasRedis = data?.runtime_status?.connection_status === 'connected'
    const hasSqlite = data?.sqlite_status?.connection_status === 'connected'
    const isRedisRuntime = data?.runtime_status?.mode === 'redis'
    const isLlmReady = data?.llm_status?.gateway_status === 'ready'
    const isRecovering = data?.runtime_status?.recovering === true

    let overall: OverallHealthType = 'Healthy'
    if (!hasSqlite) {
      overall = 'Critical'
    } else if (!isRedisRuntime || !hasRedis || !isLlmReady) {
      overall = 'Degraded'
    }

    let runtimeState = 'Redis Active'
    if (isRecovering) {
      runtimeState = 'Recovering'
    } else if (!isRedisRuntime) {
      runtimeState = 'Memory Fallback'
    }

    return {
      overall,
      fastapi: { value: 'Online', status: 'healthy' as StatusType },
      runtime: {
        value: runtimeState,
        status: isRedisRuntime
          ? ('healthy' as StatusType)
          : isRecovering
          ? ('warning' as StatusType)
          : ('warning' as StatusType),
      },
      sqlite: {
        value: hasSqlite ? 'Connected' : 'Disconnected',
        status: hasSqlite ? ('healthy' as StatusType) : ('critical' as StatusType),
      },
      redis: {
        value: hasRedis ? 'Connected' : 'Disconnected',
        status: hasRedis ? ('healthy' as StatusType) : ('warning' as StatusType),
      },
      llm: {
        value: isLlmReady ? 'Ready' : 'Unavailable',
        status: isLlmReady ? ('healthy' as StatusType) : ('warning' as StatusType),
      },
      qualityGates: {
        value: data?.repository_status?.quality_gates === 'passed' ? 'Passed' : 'Failed',
        status: data?.repository_status?.quality_gates === 'passed' ? ('healthy' as StatusType) : ('critical' as StatusType),
      },
      runtimeState,
    }
  }, [data, loading, isOffline])

  const generateReportText = (): string => {
    const hasRedis = data?.runtime_status?.connection_status === 'connected'
    const hasSqlite = data?.sqlite_status?.connection_status === 'connected'
    return [
      `Application: ${isOffline ? 'Offline' : 'Online'}`,
      `Runtime: ${states.runtime.value}`,
      `Redis: ${hasRedis ? 'Connected' : 'Disconnected'}`,
      `SQLite: ${hasSqlite ? 'Connected' : 'Disconnected'}`,
      `Provider: ${data?.llm_status?.provider || 'Gemini'}`,
      `Quality Gates: ${states.qualityGates.value}`,
    ].join('\n')
  }

  const handleCopy = async () => {
    try {
      const text = generateReportText()
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Graceful fallback if clipboard API fails/mocked out
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleExport = () => {
    try {
      const text = generateReportText()
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'diagnostics.txt'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed: ', err)
    }
  }

  const handleOpenDetails = () => {
    setIsModalOpen(true)
    if (onViewDetails) {
      onViewDetails()
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const rowIndicator = (status: StatusType | 'gray' | 'failed') => {
    const bgMap = {
      healthy: 'bg-emerald-500 shadow-[0_0_8px_#10b981]',
      warning: 'bg-amber-500 shadow-[0_0_8px_#f59e0b]',
      critical: 'bg-red-500 shadow-[0_0_8px_#ef4444]',
      failed: 'bg-red-500 shadow-[0_0_8px_#ef4444]',
      loading: 'bg-indigo-500 animate-pulse',
      gray: 'bg-slate-600',
    }
    return <span className={`w-2 h-2 rounded-full inline-block ${bgMap[status]}`} />
  }

  return (
    <>
      <Card className="p-6 space-y-4 flex flex-col justify-between h-full min-h-[360px]">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            <span role="img" aria-label="diagnostics icon">🏥</span> Status Diagnostics
          </h2>
          <HealthBadge status={states.overall} />
        </div>
        
        <Divider className="my-1" />

        {/* Rows */}
        <div className="flex-grow space-y-1">
          <StatusRow label="FastAPI" value={states.fastapi.value} status={states.fastapi.status} />
          <StatusRow label="Runtime" value={states.runtime.value} status={states.runtime.status} />
          <StatusRow label="SQLite" value={states.sqlite.value} status={states.sqlite.status} />
          <StatusRow label="Redis" value={states.redis.value} status={states.redis.status} />
          <StatusRow label="LLM" value={states.llm.value} status={states.llm.status} />
          <StatusRow label="Quality Gates" value={states.qualityGates.value} status={states.qualityGates.status} />
        </div>

        {/* Footer */}
        <div className="pt-2">
          <Button
            variant="outline"
            className="w-full text-xs py-2 hover:bg-slate-800/80 cursor-pointer"
            onClick={handleOpenDetails}
            aria-label="View Details"
          >
            View Details
          </Button>
        </div>
      </Card>

      {/* Rebuilt Detailed Diagnostics Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onClick={() => setIsModalOpen(false)}
        >
          <div
            ref={modalRef}
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full max-h-[85vh] flex flex-col shadow-2xl text-left animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Sticky Header */}
            <div className="sticky top-0 bg-slate-900 z-10 px-6 py-4 border-b border-slate-850 flex items-center justify-between">
              <h3 id="modal-title" className="text-lg font-bold text-white flex items-center gap-2">
                <span>🏥</span> Detailed Diagnostics Panel
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800/60 transition-all cursor-pointer"
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            {/* Quick Action Toolbar */}
            <div className="px-6 py-3 bg-slate-950/20 border-b border-slate-800/60 flex flex-wrap gap-2 justify-between items-center">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchHealth(true)}
                  disabled={refreshing}
                  className="text-xs flex items-center gap-1.5 cursor-pointer"
                  aria-label="Refresh diagnostics"
                >
                  {refreshing ? <Spinner size="sm" className="inline" /> : '🔄'}
                  <span>Refresh</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopy}
                  className="text-xs flex items-center gap-1.5 cursor-pointer"
                  aria-label="Copy report to clipboard"
                >
                  {copied ? '✅' : '📋'}
                  <span>{copied ? 'Copied!' : 'Copy'}</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExport}
                  className="text-xs flex items-center gap-1.5 cursor-pointer"
                  aria-label="Export report as file"
                >
                  📥
                  <span>Export</span>
                </Button>
              </div>
              <span className="text-[10px] text-slate-500 font-medium">Auto-polls every 10s</span>
            </div>

            {/* Scrollable Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
              {/* Section 1 — Overall Status */}
              <CollapsibleSection
                title="Section 1 — Overall Status"
                icon="📋"
                isOpen={expandedSections.overall}
                onToggle={() => toggleSection('overall')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Overall Health</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.overall === 'Healthy' ? 'healthy' : states.overall === 'Degraded' ? 'warning' : states.overall === 'Checking' ? 'loading' : 'critical')}
                    <span className="font-semibold text-slate-200">{states.overall}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Application Status</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.fastapi.status)}
                    <span className="font-semibold text-slate-200">{states.fastapi.value}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Runtime Mode</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.runtime.status)}
                    <span className="font-semibold text-slate-200">{states.runtime.value}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Last Updated</span>
                  <span className="font-mono text-slate-200">{lastUpdated}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Startup Time</span>
                  <span className="font-mono text-slate-200">{data?.startup_time || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">Application Version</span>
                  <span className="font-mono text-slate-200">{data?.version || 'Unknown'}</span>
                </div>
              </CollapsibleSection>

              {/* Section 2 — Application */}
              <CollapsibleSection
                title="Section 2 — Application"
                icon="💻"
                isOpen={expandedSections.app}
                onToggle={() => toggleSection('app')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">FastAPI Status</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.fastapi.status)}
                    <span className="font-semibold text-slate-200">{states.fastapi.value}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Environment</span>
                  <span className="font-semibold text-slate-200 capitalize">{data?.environment || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Debug Mode</span>
                  <span className="font-semibold text-slate-200">{data ? (data.debug_mode ? 'True' : 'False') : 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Application Version</span>
                  <span className="font-mono text-slate-200">{data?.version || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Python Version</span>
                  <span className="font-mono text-slate-200">{data?.python_version || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">API Response Time</span>
                  <span className="font-mono text-slate-200">{responseTimeMs !== null ? `${responseTimeMs} ms` : 'Loading...'}</span>
                </div>
              </CollapsibleSection>

              {/* Section 3 — Runtime */}
              <CollapsibleSection
                title="Section 3 — Runtime"
                icon="⚙️"
                isOpen={expandedSections.runtime}
                onToggle={() => toggleSection('runtime')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Runtime Provider</span>
                  <span className="font-semibold text-slate-200">{data?.runtime_status?.provider || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Redis Status</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(data?.runtime_status?.redis_status === 'healthy' ? 'healthy' : 'critical')}
                    <span className="font-semibold text-slate-200">{data?.runtime_status?.redis_status === 'healthy' ? 'Connected' : 'Disconnected'}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Memory Fallback</span>
                  <span className="font-semibold text-slate-200">{data?.runtime_status?.mode === 'memory' ? 'Enabled (Active)' : 'Disabled'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Recovery Monitor</span>
                  <span className="font-semibold text-slate-200">{data?.runtime_status?.mode === 'memory' ? 'Running' : 'Idle'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Reconnect Count</span>
                  <span className="font-mono text-slate-200">{data?.runtime_status?.reconnect_count ?? 0}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Last Recovery Time</span>
                  <span className="font-mono text-slate-200">{data?.runtime_status?.last_reconnection_time || 'None'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">Runtime State</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.runtime.status)}
                    <span className="font-semibold text-slate-200">{states.runtimeState}</span>
                  </div>
                </div>
              </CollapsibleSection>

              {/* Section 4 — Persistence */}
              <CollapsibleSection
                title="Section 4 — Persistence"
                icon="💾"
                isOpen={expandedSections.persistence}
                onToggle={() => toggleSection('persistence')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">SQLite Status</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(states.sqlite.status)}
                    <span className="font-semibold text-slate-200">{states.sqlite.value}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">SQLite Path</span>
                  <span className="font-mono text-slate-200 break-all pl-4 text-right">{data?.sqlite_status?.database_path || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Database Size</span>
                  <span className="font-mono text-slate-200">{data?.sqlite_status?.database_size_bytes !== undefined ? formatBytes(data.sqlite_status.database_size_bytes) : 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Persistence Provider</span>
                  <span className="font-semibold text-slate-200">SQLitePersistenceProvider</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Artifact Provider</span>
                  <span className="font-semibold text-slate-200">DiskArtifactProvider</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">Dataset Provider</span>
                  <span className="font-semibold text-slate-200">DiskDatasetStorageManager</span>
                </div>
              </CollapsibleSection>

              {/* Section 5 — AI Services */}
              <CollapsibleSection
                title="Section 5 — AI Services"
                icon="🤖"
                isOpen={expandedSections.ai}
                onToggle={() => toggleSection('ai')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Provider</span>
                  <span className="font-semibold text-slate-200">{data?.llm_status?.provider || 'Gemini'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Model</span>
                  <span className="font-mono text-slate-200">{data?.llm_status?.model || 'gemini-1.5-pro'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Gateway Status</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(data?.llm_status?.gateway_status === 'ready' ? 'healthy' : 'warning')}
                    <span className="font-semibold text-slate-200">{data?.llm_status?.gateway_status === 'ready' ? 'Ready' : 'API Key Configured (No)'}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Retry Count</span>
                  <span className="font-mono text-slate-200">{data?.llm_status?.retry_count ?? 3}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Timeout</span>
                  <span className="font-mono text-slate-200">{data?.llm_status?.timeout ?? 30} s</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">API Key Configured</span>
                  <span className="font-semibold text-slate-200">{data?.llm_status?.api_key_configured ? 'Yes' : 'No'}</span>
                </div>
              </CollapsibleSection>

              {/* Section 6 — Repository */}
              <CollapsibleSection
                title="Section 6 — Repository"
                icon="📁"
                isOpen={expandedSections.repo}
                onToggle={() => toggleSection('repo')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Git Branch</span>
                  <span className="font-mono text-slate-200">{data?.repository_status?.git_branch || 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Quality Gates</span>
                  <div className="flex items-center gap-2">
                    {rowIndicator(data?.repository_status?.quality_gates === 'passed' ? 'healthy' : 'critical')}
                    <span className="font-semibold text-slate-200 capitalize">{data?.repository_status?.quality_gates || 'Passed'}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Verification Stamp</span>
                  <span className="font-semibold text-slate-200 capitalize">{data?.repository_status?.verification_stamp || 'Verified'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Working Tree Status</span>
                  <span className="font-semibold text-slate-200 capitalize">{data?.repository_status?.working_tree_status || 'Clean'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">Merge Conflicts</span>
                  <span className="font-semibold text-slate-200 capitalize">{data?.repository_status?.merge_conflicts || 'None'}</span>
                </div>
              </CollapsibleSection>

              {/* Section 7 — Performance */}
              <CollapsibleSection
                title="Section 7 — Performance"
                icon="⚡"
                isOpen={expandedSections.perf}
                onToggle={() => toggleSection('perf')}
              >
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">Application Uptime</span>
                  <span className="font-mono text-slate-200">{data?.uptime !== undefined ? `${data.uptime} s` : 'Unknown'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">API Response Time</span>
                  <span className="font-mono text-slate-200">{responseTimeMs !== null ? `${responseTimeMs} ms` : 'Loading...'}</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                  <span className="text-slate-400">SQLite Latency</span>
                  <span className="font-mono text-slate-200">{data?.performance_metrics?.sqlite_latency_ms !== undefined ? `${data.performance_metrics.sqlite_latency_ms} ms` : 'Unknown'}</span>
                </div>
                {data?.performance_metrics?.redis_latency_ms !== undefined && data.performance_metrics.redis_latency_ms !== null && (
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/20 text-xs">
                    <span className="text-slate-400">Redis Latency</span>
                    <span className="font-mono text-slate-200">{data.performance_metrics.redis_latency_ms} ms</span>
                  </div>
                )}
                <div className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-slate-400">Last Health Refresh</span>
                  <span className="font-mono text-slate-200">{lastUpdated}</span>
                </div>
              </CollapsibleSection>

              {/* Section 8 — Recent Runtime Events */}
              <CollapsibleSection
                title="Recent Runtime Events"
                icon="⏱️"
                isOpen={expandedSections.events}
                onToggle={() => toggleSection('events')}
              >
                {runtimeEvents.length === 0 ? (
                  <div className="text-center py-4 text-slate-500 text-xs select-none">
                    No runtime events recorded.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                    {runtimeEvents.map((evt, idx) => (
                      <div key={idx} className="flex justify-between items-center text-xs py-1.5 border-b border-slate-850 last:border-0">
                        <span className="font-medium text-slate-300">{evt.event}</span>
                        <span className="font-mono text-slate-500 text-[10px]">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CollapsibleSection>
            </div>

            {/* Sticky Footer */}
            <div className="sticky bottom-0 bg-slate-900 border-t border-slate-850 px-6 py-4 flex justify-end">
              <Button
                variant="secondary"
                onClick={() => setIsModalOpen(false)}
                aria-label="Close detailed diagnostics modal"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
