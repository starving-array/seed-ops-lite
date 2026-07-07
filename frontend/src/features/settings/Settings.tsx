import { useState, useEffect } from 'react'
import {
  PageHeader,
  Card,
  Button,
  Input,
  Checkbox,
  Badge,
  Spinner,
} from '../../components/ui'
import { apiClient } from '../../api/client'
import { useNotifications } from '../../context/NotificationContext'

interface LLMProviderDetails {
  name: string
  is_available: boolean
  auth_status: string
  capabilities: {
    streaming: boolean
    json_mode: boolean
    vision: boolean
    tool_calling: boolean
  }
  models: string[]
}

interface LLMConfigState {
  provider: string
  model: string
  auto_failover: boolean
  fallback_order: string[]
}

interface HealthCheckResult {
  status: 'Healthy' | 'Unavailable'
  auth?: string
  billing?: string
  latency_ms?: number
  models?: number
  version?: string
  error?: string
}

export default function Settings() {
  const [providers, setProviders] = useState<LLMProviderDetails[]>([])
  const [config, setConfig] = useState<LLMConfigState>({
    provider: 'google',
    model: 'gemini-2.5-flash',
    auto_failover: true,
    fallback_order: ['vertex', 'gemini', 'anthropic', 'openai', 'ollama'],
  })
  const [healthData, setHealthData] = useState<Record<string, HealthCheckResult>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isCheckingHealth, setIsCheckingHealth] = useState(false)

  const { addNotification } = useNotifications()

  // Load backend details
  const loadData = async () => {
    setIsLoading(true)
    try {
      const provRes = await apiClient.get<LLMProviderDetails[]>('/llm/providers')
      if (provRes.success && provRes.data) {
        setProviders(provRes.data)
      }

      const confRes = await apiClient.get<any>('/llm/config')
      if (confRes.success && confRes.data) {
        setConfig({
          provider: confRes.data.provider,
          model: confRes.data.model,
          auto_failover: confRes.data.auto_failover,
          fallback_order: confRes.data.fallback_order || [],
        })
      }
    } catch (err: any) {
      addNotification({ type: 'error', title: 'Failed to load LLM configurations' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Run manual health check
  const runHealthCheck = async () => {
    setIsCheckingHealth(true)
    try {
      const res = await apiClient.post<Record<string, HealthCheckResult>>('/llm/healthcheck')
      if (res.success && res.data) {
        setHealthData(res.data)
        addNotification({ type: 'success', title: 'Provider health checks completed successfully.' })
      } else {
        addNotification({ type: 'error', title: 'Health check execution failed.' })
      }
    } catch (err: any) {
      addNotification({ type: 'error', title: 'Error running health checks: ' + err.message })
    } finally {
      setIsCheckingHealth(false)
    }
  }

  // Save settings
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      const res = await apiClient.post('/llm/config', {
        provider: config.provider,
        model: config.model,
        auto_failover: config.auto_failover,
        fallback_order: config.fallback_order.join(','),
      })
      if (res.success) {
        addNotification({ type: 'success', title: 'LLM configurations saved and applied successfully.' })
        loadData()
      } else {
        addNotification({ type: 'error', title: 'Failed to save LLM settings.' })
      }
    } catch (err: any) {
      addNotification({ type: 'error', title: 'Error saving LLM settings: ' + err.message })
    } finally {
      setIsSaving(false)
    }
  }

  // Get active models list based on selection
  const selectedProviderDetails = providers.find(
    (p) =>
      p.name.toLowerCase().includes(config.provider.toLowerCase()) ||
      (config.provider === 'google' && p.name.toLowerCase().includes('gemini'))
  )

  const activeModelsList = selectedProviderDetails?.models || []

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="md" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto px-4 py-6">
      <PageHeader
        title="Settings"
        subtitle="Configure centralized LLM gateway models, providers, and failover options."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Form & Providers */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <div className="p-6">
              <h2 className="text-xl font-bold text-slate-100 border-b border-slate-700/50 pb-3 mb-6 flex items-center gap-2">
                ⚙️ Centralized LLM Engine Configuration
              </h2>

              <form onSubmit={handleSave} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Select Active Provider */}
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-300">
                      Active LLM Provider
                    </label>
                    <select
                      value={config.provider}
                      onChange={(e) => {
                        const nextProv = e.target.value
                        const match = providers.find(
                          (p) =>
                            p.name.toLowerCase().includes(nextProv.toLowerCase()) ||
                            (nextProv === 'google' && p.name.toLowerCase().includes('gemini'))
                        )
                        setConfig({
                          ...config,
                          provider: nextProv,
                          model: match?.models[0] || '',
                        })
                      }}
                      className="w-full h-11 px-3 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500 font-medium"
                    >
                      <option value="google">Gemini Developer API (Google)</option>
                      <option value="vertex">Vertex AI (Google Cloud)</option>
                      <option value="anthropic">Anthropic (Claude)</option>
                      <option value="openai">OpenAI (GPT)</option>
                      <option value="azure">Azure OpenAI (GPT)</option>
                      <option value="ollama">Ollama (Local Models)</option>
                    </select>
                    <p className="text-xs text-slate-500">
                      Determines which LLM interface executes all background queries.
                    </p>
                  </div>

                  {/* Select Active Model */}
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-300">
                      Primary Provider Model
                    </label>
                    <select
                      value={config.model}
                      onChange={(e) => setConfig({ ...config, model: e.target.value })}
                      className="w-full h-11 px-3 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500 font-mono text-sm"
                    >
                      {activeModelsList.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                      {activeModelsList.length === 0 && (
                        <option value="">No models available for selected provider</option>
                      )}
                    </select>
                    <p className="text-xs text-slate-500">
                      Target model identifier loaded dynamically from provider capabilities.
                    </p>
                  </div>
                </div>

                {/* Auto Failover Option */}
                <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50 space-y-4">
                  <div className="flex items-start gap-3">
                    <Checkbox
                      id="auto-failover-opt"
                      label=""
                      checked={config.auto_failover}
                      onChange={(e) => setConfig({ ...config, auto_failover: e.target.checked })}
                    />
                    <div className="space-y-1">
                      <label htmlFor="auto-failover-opt" className="text-sm font-semibold text-slate-200 cursor-pointer">
                        Enable Automatic Provider Failover (LLM_AUTO_FAILOVER)
                      </label>
                      <p className="text-xs text-slate-400">
                        When enabled, if the active provider experiences outages, quotas limit, or credentials failure, the gateway will try fallback options sequentially.
                      </p>
                    </div>
                  </div>

                  {config.auto_failover && (
                    <div className="pt-3 border-t border-slate-700/50 space-y-2">
                      <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                        Failover Fallback Order Priority
                      </label>
                      <Input
                        type="text"
                        value={config.fallback_order.join(', ')}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            fallback_order: e.target.value.split(',').map((x) => x.trim()),
                          })
                        }
                        className="font-mono text-xs text-slate-300"
                        placeholder="e.g. gemini, vertex, anthropic, openai, ollama"
                      />
                      <p className="text-xxs text-slate-500 leading-relaxed">
                        Comma-separated list of provider tags to try next if the active provider fails. Supported keys: google, vertex, anthropic, openai, azure, ollama.
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-700/50">
                  <div className="text-xs text-slate-400 flex items-center gap-1.5">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    Credentials status: Config resolved cleanly
                  </div>
                  <Button variant="primary" type="submit" disabled={isSaving}>
                    {isSaving ? <Spinner size="sm" /> : 'Save Configurations'}
                  </Button>
                </div>
              </form>
            </div>
          </Card>

          {/* Provider Status Diagnostic Panel */}
          <Card>
            <div className="p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-700/50 pb-3">
                <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                  🔌 Registry Diagnostic Status
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={runHealthCheck}
                  disabled={isCheckingHealth}
                >
                  {isCheckingHealth ? <Spinner size="sm" /> : '⚔️ Run Health Check'}
                </Button>
              </div>

              <div className="space-y-4">
                {providers.map((p) => {
                  const check = healthData[p.name]
                  const hasRan = !!check

                  let statusBadge = <Badge variant="info">Not Checked</Badge>
                  if (hasRan) {
                    statusBadge =
                      check.status === 'Healthy' ? (
                        <Badge variant="success">Healthy</Badge>
                      ) : (
                        <Badge variant="error">Unavailable</Badge>
                      )
                  } else if (p.is_available) {
                    statusBadge = <Badge variant="warning">Ready</Badge>
                  } else {
                    statusBadge = <Badge variant="error">Missing Config</Badge>
                  }

                  return (
                    <div
                      key={p.name}
                      className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-200">{p.name}</span>
                          {statusBadge}
                        </div>
                        <div className="text-xs text-slate-400">
                          Auth status: <span className="text-slate-300 font-medium">{p.auth_status}</span>
                        </div>
                        {hasRan && check.error && (
                          <div className="text-xs text-red-400 font-mono mt-1">
                            Error: {check.error}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-6 text-xs text-slate-400">
                        {hasRan && check.status === 'Healthy' && (
                          <>
                            <div>
                              Latency:{' '}
                              <span className="text-emerald-400 font-mono">
                                {check.latency_ms} ms
                              </span>
                            </div>
                            <div>
                              Models:{' '}
                              <span className="text-slate-200 font-semibold">{check.models}</span>
                            </div>
                          </>
                        )}
                        <div className="flex gap-1">
                          {p.capabilities.json_mode && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-700/60 text-xxs text-slate-300">
                              JSON
                            </span>
                          )}
                          {p.capabilities.vision && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-700/60 text-xxs text-slate-300">
                              Vision
                            </span>
                          )}
                          {p.capabilities.tool_calling && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-700/60 text-xxs text-slate-300">
                              Tools
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </Card>
        </div>

        {/* Right Hand: Info sidebar / Current Active Values */}
        <div className="space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-200 border-b border-slate-700/50 pb-2">
                Active Provider Details
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">Provider</span>
                  <span className="text-slate-200 font-semibold uppercase">{config.provider}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Model</span>
                  <span className="text-slate-200 font-mono">{config.model}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Failover Cache</span>
                  <span className="text-slate-200">
                    {config.auto_failover ? 'Enabled ✅' : 'Disabled ❌'}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6 space-y-3">
              <h3 className="text-lg font-bold text-slate-200 border-b border-slate-700/50 pb-2">
                💡 Configuration Help
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Configurations are resolved instantly at runtime from Advanced Settings (persisted to SQLite). To customize default credentials, populate your local <code>.env</code> file. No application restart is needed when changing models or providers from this settings dashboard.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
