import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { StatusDiagnosticsCard } from './StatusDiagnosticsCard'
import type { RuntimeEvent } from './StatusDiagnosticsCard'
import type { HealthReport } from '../../services/health'

const mockHealthData: HealthReport = {
  status: 'healthy',
  version: '1.0.0',
  environment: 'development',
  uptime: 123.45,
  python_version: '3.13.14',
  redis_status: 'healthy',
  startup_time: '2026-07-03T22:00:00Z',
  storage_mode: 'redis',
  sqlite_status: {
    status: 'healthy',
    migration_version: 'v1',
    database_path: 'test.db',
    connection_status: 'connected',
    initialized: true,
    migration_status: 'completed',
    pending_migrations: [],
    last_successful_migration_at: '2026-07-03T22:00:00Z',
    database_size_bytes: 4096,
  },
  runtime_status: {
    provider: 'RedisRuntimeProvider',
    redis_status: 'healthy',
    connection_status: 'connected',
    reconnect_count: 0,
    mode: 'redis',
    last_reconnection_time: null,
    recovering: false,
  },
  services: {
    redis: { status: 'healthy' },
    sqlite: { status: 'healthy' },
  },
  debug_mode: true,
  llm_status: {
    provider: 'Gemini',
    model: 'gemini-2.5-flash',
    gateway_status: 'ready',
    retry_count: 3,
    timeout: 30,
    api_key_configured: true,
  },
  repository_status: {
    git_branch: 'main',
    quality_gates: 'passed',
    verification_stamp: 'verified',
    working_tree_status: 'clean',
    merge_conflicts: 'none',
  },
  performance_metrics: {
    sqlite_latency_ms: 0.123,
    redis_latency_ms: 1.245,
  },
}

const mockTimelineEvents: RuntimeEvent[] = [
  { event: 'Redis Connected', timestamp: '2026-07-03T22:01:00Z' },
  { event: 'Application Started', timestamp: '2026-07-03T22:00:00Z' },
]

describe('StatusDiagnosticsCard Component Tests', () => {
  it('should render loading state correctly', () => {
    const html = renderToStaticMarkup(<StatusDiagnosticsCard mockLoading={true} />)
    expect(html).toContain('Status Diagnostics')
    expect(html).toContain('Checking')
    expect(html).toContain('Loading')
  })

  it('should render healthy state correctly', () => {
    const html = renderToStaticMarkup(<StatusDiagnosticsCard mockData={mockHealthData} mockLoading={false} />)
    expect(html).toContain('Status Diagnostics')
    expect(html).toContain('Healthy')
    expect(html).toContain('Online')
    expect(html).toContain('Redis Active')
    expect(html).toContain('Connected')
  })

  it('should render degraded state correctly (Redis/Runtime down)', () => {
    const degradedData = {
      ...mockHealthData,
      runtime_status: {
        ...mockHealthData.runtime_status,
        connection_status: 'disconnected',
        mode: 'memory',
      },
    }
    const html = renderToStaticMarkup(<StatusDiagnosticsCard mockData={degradedData} mockLoading={false} />)
    expect(html).toContain('Status Diagnostics')
    expect(html).toContain('Degraded')
    expect(html).toContain('Memory Fallback')
    expect(html).toContain('Disconnected')
  })

  it('should render critical state correctly (Offline)', () => {
    const html = renderToStaticMarkup(<StatusDiagnosticsCard mockOffline={true} mockLoading={false} />)
    expect(html).toContain('Status Diagnostics')
    expect(html).toContain('Critical')
    expect(html).toContain('Offline')
    expect(html).toContain('Disconnected')
  })

  it('should render the View Details button', () => {
    const html = renderToStaticMarkup(<StatusDiagnosticsCard mockData={mockHealthData} mockLoading={false} />)
    expect(html).toContain('View Details')
  })

  it('should render the detailed modal with all sections when mockModalOpen is true', () => {
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard mockData={mockHealthData} mockLoading={false} mockModalOpen={true} />
    )
    expect(html).toContain('Detailed Diagnostics Panel')
    expect(html).toContain('Section 1 — Overall Status')
    expect(html).toContain('Section 2 — Application')
    expect(html).toContain('Section 3 — Runtime')
    expect(html).toContain('Section 4 — Persistence')
    expect(html).toContain('Section 5 — AI Services')
    expect(html).toContain('Section 6 — Repository')
    expect(html).toContain('Section 7 — Performance')
    expect(html).toContain('Recent Runtime Events')
  })

  it('should render AI services section details correctly', () => {
    const mockExpanded = { ai: true }
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard
        mockData={mockHealthData}
        mockLoading={false}
        mockModalOpen={true}
        mockExpandedSections={mockExpanded}
      />
    )
    expect(html).toContain('Provider')
    expect(html).toContain('Gemini')
    expect(html).toContain('Model')
    expect(html).toContain('gemini-2.5-flash')
    expect(html).toContain('Retry Count')
    expect(html).toContain('Timeout')
    expect(html).toContain('API Key Configured')
  })

  it('should render repository section details correctly', () => {
    const mockExpanded = { repo: true }
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard
        mockData={mockHealthData}
        mockLoading={false}
        mockModalOpen={true}
        mockExpandedSections={mockExpanded}
      />
    )
    expect(html).toContain('Git Branch')
    expect(html).toContain('main')
    expect(html).toContain('Quality Gates')
    expect(html).toContain('Verification Stamp')
    expect(html).toContain('Working Tree Status')
    expect(html).toContain('Merge Conflicts')
  })

  it('should render performance section details correctly', () => {
    const mockExpanded = { perf: true }
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard
        mockData={mockHealthData}
        mockLoading={false}
        mockModalOpen={true}
        mockExpandedSections={mockExpanded}
      />
    )
    expect(html).toContain('Application Uptime')
    expect(html).toContain('SQLite Latency')
    expect(html).toContain('Redis Latency')
    expect(html).toContain('Last Health Refresh')
  })

  it('should render timeline events correctly', () => {
    const mockExpanded = { events: true }
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard
        mockData={mockHealthData}
        mockLoading={false}
        mockModalOpen={true}
        mockExpandedSections={mockExpanded}
        mockEvents={mockTimelineEvents}
      />
    )
    expect(html).toContain('Redis Connected')
    expect(html).toContain('Application Started')
  })

  it('should only show children for expanded sections', () => {
    const mockExpanded = {
      overall: true,
      app: false,
      runtime: false,
      persistence: false,
      ai: false,
      repo: false,
      perf: false,
      events: false,
    }
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard
        mockData={mockHealthData}
        mockLoading={false}
        mockModalOpen={true}
        mockExpandedSections={mockExpanded}
      />
    )
    expect(html).toContain('Overall Health')
    expect(html).toContain('Startup Time')
    
    expect(html).not.toContain('FastAPI Status')
    expect(html).not.toContain('Python Version')
    expect(html).not.toContain('Reconnect Count')
    expect(html).not.toContain('SQLite Path')
  })

  it('should have action buttons: Refresh, Copy, Export', () => {
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard mockData={mockHealthData} mockLoading={false} mockModalOpen={true} />
    )
    expect(html).toContain('Refresh')
    expect(html).toContain('Copy')
    expect(html).toContain('Export')
  })

  it('should have correct accessibility attributes in the modal', () => {
    const html = renderToStaticMarkup(
      <StatusDiagnosticsCard mockData={mockHealthData} mockLoading={false} mockModalOpen={true} />
    )
    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-modal="true"')
    expect(html).toContain('aria-labelledby="modal-title"')
    expect(html).toContain('aria-expanded="true"') // Section 1 is open by default
  })
})
