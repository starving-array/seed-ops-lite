import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Button,
  Card,
  Input,
  Select,
  Badge,
  Divider,
  Alert,
  Spinner,
} from '../../components/ui'
import { schemaService } from '../../services/schema'
import type { Job } from '../../services/schema'
import { useNotifications } from '../../context/NotificationContext'

export const JobHistory = () => {
  const { addNotification } = useNotifications()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('all') // all, today, week

  // Refs for tracking job status changes for notifications
  const prevJobsRef = useRef<Record<string, string>>({})
  const pollingRef = useRef<any>(null)

  // Fetch jobs function
  const fetchJobs = useCallback(
    async (showLoading = false) => {
      if (showLoading) setLoading(true)
      try {
        const response = await schemaService.listJobs({
          status: statusFilter || undefined,
          job_type: typeFilter || undefined,
          search: searchQuery || undefined,
        })

        if (response.success && response.data) {
          const freshJobs = response.data

          // Apply local date filter if selected
          const filtered = freshJobs.filter((job) => {
            if (dateFilter === 'all') return true
            const startedAtDate = new Date(job.startedAt)
            const now = new Date()
            if (dateFilter === 'today') {
              return startedAtDate.toDateString() === now.toDateString()
            }
            if (dateFilter === 'week') {
              const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
              return startedAtDate >= oneWeekAgo
            }
            return true
          })

          setJobs(filtered)

          // Notification checks on status transitions
          filtered.forEach((job) => {
            const prevStatus = prevJobsRef.current[job.jobId]
            if (prevStatus && prevStatus !== job.status) {
              if (job.status === 'Completed') {
                addNotification({
                  type: 'success',
                  title: 'Background Job Succeeded',
                  message: `Job ${job.jobId.slice(0, 8)} (${job.type}) finished successfully.`,
                })
              } else if (job.status === 'Failed') {
                addNotification({
                  type: 'error',
                  title: 'Background Job Failed',
                  message: `Job ${job.jobId.slice(0, 8)} failed: ${job.errorMessage || 'Unknown error'}`,
                })
              } else if (job.status === 'Cancelled') {
                addNotification({
                  type: 'warning',
                  title: 'Background Job Cancelled',
                  message: `Job ${job.jobId.slice(0, 8)} was aborted by user.`,
                })
              }
            }
            prevJobsRef.current[job.jobId] = job.status
          })

          // Keep selected job reference fresh
          if (selectedJob) {
            const updatedSelected = freshJobs.find((j) => j.jobId === selectedJob.jobId)
            if (updatedSelected) {
              setSelectedJob(updatedSelected)
            }
          }
        }
      } catch (err: any) {
        console.error('Error fetching jobs:', err)
      } finally {
        if (showLoading) setLoading(false)
      }
    },
    [searchQuery, statusFilter, typeFilter, dateFilter, selectedJob, addNotification]
  )

  // Poll job list for real-time monitoring
  useEffect(() => {
    fetchJobs(true)
    pollingRef.current = setInterval(() => {
      fetchJobs(false)
    }, 3000)

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [fetchJobs])

  // Actions
  const handleCancelJob = async (jobId: string) => {
    try {
      const response = await schemaService.cancelJob(jobId)
      if (response.success) {
        addNotification({
          type: 'warning',
          title: 'Cancellation Signal Sent',
          message: `Sent abort command for job ${jobId.slice(0, 8)}.`,
        })
        fetchJobs(false)
      } else {
        addNotification({
          type: 'error',
          title: 'Cancellation Failed',
          message: response.error?.message || 'Could not cancel job.',
        })
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'API Request Failed',
        message: err.message || 'Error occurred while requesting cancellation.',
      })
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Queued':
        return <Badge variant="info">Queued</Badge>
      case 'Running':
        return <Badge variant="info" className="animate-pulse">Running</Badge>
      case 'Completed':
        return <Badge variant="success">Completed</Badge>
      case 'Failed':
        return <Badge variant="error">Failed</Badge>
      case 'Cancelled':
        return <Badge variant="warning">Cancelled</Badge>
      default:
        return <Badge variant="info">{status}</Badge>
    }
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Job History</h1>
          <p className="text-sm text-slate-400 mt-1.5">
            Monitor, inspect, and audit active or historical relational generation workloads.
          </p>
        </div>
        <Button variant="secondary" onClick={() => fetchJobs(true)}>
          🔄 Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ==================== LEFT: FILTERS & JOB LIST ==================== */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="p-4 bg-slate-900/40 border-slate-800/80 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <div className="md:col-span-2">
                <Input
                  id="search"
                  placeholder="Search by ID or type..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="py-1.5"
                />
              </div>
              <Select
                id="typeFilter"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                options={[
                  { value: '', label: 'All Types' },
                  { value: 'generation', label: 'Generation' },
                ]}
                className="py-1.5"
              />
              <Select
                id="statusFilter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={[
                  { value: '', label: 'All Statuses' },
                  { value: 'queued', label: 'Queued' },
                  { value: 'running', label: 'Running' },
                  { value: 'completed', label: 'Completed' },
                  { value: 'failed', label: 'Failed' },
                  { value: 'cancelled', label: 'Cancelled' },
                ]}
                className="py-1.5"
              />
              <Select
                id="dateFilter"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                options={[
                  { value: 'all', label: 'All Dates' },
                  { value: 'today', label: 'Today' },
                  { value: 'week', label: 'Last 7 Days' },
                ]}
                className="py-1.5"
              />
            </div>
          </Card>

          {loading ? (
            <div className="flex flex-col items-center justify-center p-20 gap-3">
              <Spinner size="lg" />
              <span className="text-sm text-slate-400">Fetching jobs history audit logs...</span>
            </div>
          ) : jobs.length === 0 ? (
            <Card className="p-12 text-center text-slate-500 border-slate-850">
              <span className="text-4xl block mb-3">📁</span>
              <p className="text-sm font-semibold text-slate-400">No Job Logs Found</p>
              <p className="text-xs text-slate-500 mt-1">
                Initiate a synthetics generation run or adjust filters to view historical job traces.
              </p>
            </Card>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {jobs.map((job) => {
                const isSelected = selectedJob?.jobId === job.jobId
                return (
                  <div
                    key={job.jobId}
                    onClick={() => setSelectedJob(job)}
                    className={`
                      p-4 rounded-2xl border transition-all cursor-pointer text-left
                      ${
                        isSelected
                          ? 'bg-indigo-950/20 border-indigo-500/50 shadow-md shadow-indigo-500/5'
                          : 'bg-slate-900/30 border-slate-850 hover:border-slate-700/60'
                      }
                    `}
                  >
                    <div className="flex justify-between items-start gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold font-mono text-indigo-400">
                            {job.jobId.slice(0, 8)}
                          </span>
                          <span className="text-xs text-slate-500">•</span>
                          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                            {job.type}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-200">
                          {job.resultSummary || 'Running synthetic generation workflow'}
                        </h4>
                        <p className="text-[10px] text-slate-500">
                          Started: {new Date(job.startedAt).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2 shrink-0">
                        {getStatusBadge(job.status)}
                        <span className="text-xs font-mono font-bold text-slate-400">
                          {job.duration.toFixed(1)}s
                        </span>
                      </div>
                    </div>

                    {/* Simple inline progress bar for running jobs */}
                    {job.status === 'Running' && (
                      <div className="mt-3.5 space-y-1.5">
                        <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-850">
                          <div
                            className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* ==================== RIGHT: JOB DETAILS ==================== */}
        <div className="lg:col-span-5">
          {selectedJob ? (
            <Card className="p-6 bg-slate-900/40 border-slate-850 text-left space-y-6">
              <div className="flex justify-between items-start gap-4 border-b border-slate-800/60 pb-4">
                <div className="space-y-1">
                  <span className="text-[10px] bg-slate-800 text-slate-400 py-0.5 px-2.5 rounded-full font-bold uppercase tracking-wide border border-slate-700/50">
                    Job ID: {selectedJob.jobId.slice(0, 8)}
                  </span>
                  <h3 className="text-base font-bold text-white uppercase tracking-wider mt-1.5">
                    {selectedJob.type} Job Details
                  </h3>
                </div>
                {getStatusBadge(selectedJob.status)}
              </div>

              {/* Stats Block */}
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3 bg-slate-950/30 rounded-xl border border-slate-850">
                  <span className="text-slate-500 block mb-0.5">Execution Duration</span>
                  <span className="font-bold text-slate-200 font-mono text-sm">
                    {selectedJob.duration.toFixed(1)}s
                  </span>
                </div>
                <div className="p-3 bg-slate-950/30 rounded-xl border border-slate-850">
                  <span className="text-slate-500 block mb-0.5">Operation Owner</span>
                  <span className="font-bold text-slate-200 text-sm">
                    {selectedJob.owner}
                  </span>
                </div>
                <div className="p-3 bg-slate-950/30 rounded-xl border border-slate-850">
                  <span className="text-slate-500 block mb-0.5">Start Time</span>
                  <span className="font-semibold text-slate-300 font-mono text-[10px]">
                    {new Date(selectedJob.startedAt).toLocaleTimeString()}
                  </span>
                </div>
                <div className="p-3 bg-slate-950/30 rounded-xl border border-slate-850">
                  <span className="text-slate-500 block mb-0.5">Progress</span>
                  <span className="font-bold text-indigo-400 font-mono text-sm">
                    {selectedJob.progress}%
                  </span>
                </div>
              </div>

              {/* Error Alert Box if failed */}
              {selectedJob.status === 'Failed' && (
                <Alert variant="error" title="Workflow Failure Log">
                  {selectedJob.errorMessage || 'Relational generation workflow halted due to missing key references.'}
                </Alert>
              )}

              {/* Timeline list */}
              <Divider label="Job Timeline" />
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Timeline
                </h4>
                <div className="space-y-3 text-xs pl-2 border-l border-slate-800">
                  <div className="relative pl-4">
                    <span className="absolute -left-[13px] top-1 w-2 h-2 rounded-full bg-indigo-500" />
                    <span className="text-slate-400">Queued</span>
                    <p className="text-[10px] text-slate-600 font-mono">
                      {new Date(selectedJob.startedAt).toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="relative pl-4">
                    <span className={`absolute -left-[13px] top-1 w-2 h-2 rounded-full ${selectedJob.status !== 'Queued' ? 'bg-indigo-500' : 'bg-slate-800'}`} />
                    <span className="text-slate-400">Running / Generating</span>
                  </div>
                  <div className="relative pl-4 pb-1">
                    <span
                      className={`absolute -left-[13px] top-1 w-2 h-2 rounded-full ${
                        selectedJob.status === 'Completed'
                          ? 'bg-emerald-500'
                          : selectedJob.status === 'Failed'
                            ? 'bg-red-500'
                            : selectedJob.status === 'Cancelled'
                              ? 'bg-amber-500'
                              : 'bg-slate-800'
                      }`}
                    />
                    <span className="text-slate-400">
                      {selectedJob.status === 'Completed'
                        ? 'Completed Successfully'
                        : selectedJob.status === 'Failed'
                          ? 'Execution Halted'
                          : selectedJob.status === 'Cancelled'
                            ? 'Cancelled'
                            : 'Finished'}
                    </span>
                    {selectedJob.finishedAt && (
                      <p className="text-[10px] text-slate-600 font-mono">
                        {new Date(selectedJob.finishedAt).toLocaleTimeString()}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Table-specific Row counts if details are present */}
              {selectedJob.details?.progress && selectedJob.details.progress.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Generated Row Counts
                  </h4>
                  <div className="space-y-2 max-h-[150px] overflow-y-auto pr-1">
                    {selectedJob.details.progress.map((p) => (
                      <div
                        key={p.tableName}
                        className="flex justify-between items-center p-2 bg-slate-950/20 border border-slate-850 rounded-lg text-xs"
                      >
                        <span className="font-semibold text-slate-400">📊 {p.tableName}</span>
                        <span className="font-mono text-slate-200">
                          {p.rowsGenerated} / {p.targetRows} rows
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Logs placeholder */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Workflow Execution Traces
                </h4>
                <div className="p-3 bg-slate-950 border border-slate-850 rounded-xl font-mono text-[10px] text-indigo-300 max-h-[160px] overflow-y-auto space-y-1.5 select-text">
                  <p className="text-slate-500">[{new Date(selectedJob.startedAt).toLocaleTimeString()}] [INFO] Starting topological generation workflow.</p>
                  <p className="text-slate-500">[{new Date(selectedJob.startedAt).toLocaleTimeString()}] [INFO] Resolved dependency tree layers successfully.</p>
                  {selectedJob.details?.progress?.map((p) => {
                    if (p.status === 'Completed') {
                      return (
                        <p key={p.tableName} className="text-emerald-400">
                          [INFO] Table Seeding completed: {p.tableName} ({p.targetRows} records generated).
                        </p>
                      )
                    }
                    if (p.status === 'Running') {
                      return (
                        <p key={p.tableName} className="text-indigo-400 animate-pulse">
                          [INFO] Seeding in progress: {p.tableName} ({p.rowsGenerated}/{p.targetRows}).
                        </p>
                      )
                    }
                    if (p.status === 'Failed') {
                      return (
                        <p key={p.tableName} className="text-red-400">
                          [ERROR] Seeding failed for table {p.tableName}: {p.error || 'Check relationship keys.'}
                        </p>
                      )
                    }
                    return null
                  })}
                  {selectedJob.status === 'Completed' && (
                    <p className="text-emerald-400">
                      [{selectedJob.finishedAt ? new Date(selectedJob.finishedAt).toLocaleTimeString() : ''}] [SUCCESS] Synthetic seeding run complete.
                    </p>
                  )}
                  {selectedJob.status === 'Cancelled' && (
                    <p className="text-amber-400">
                      [{selectedJob.finishedAt ? new Date(selectedJob.finishedAt).toLocaleTimeString() : ''}] [WARNING] Generation process cancelled by administrator.
                    </p>
                  )}
                </div>
              </div>

              {/* Cancellation button for active drawered job */}
              {(selectedJob.status === 'Queued' || selectedJob.status === 'Running') && (
                <Button
                  variant="danger"
                  className="w-full flex items-center justify-center gap-1.5"
                  onClick={() => handleCancelJob(selectedJob.jobId)}
                >
                  🛑 Terminate Active Job
                </Button>
              )}
            </Card>
          ) : (
            <Card className="p-12 text-center text-slate-500 border-slate-850 h-full flex flex-col justify-center items-center">
              <span className="text-4xl block mb-2">🔍</span>
              <p className="text-sm font-semibold text-slate-400">Select a Job</p>
              <p className="text-xs text-slate-500 mt-1">
                Click on any job entry in the history list to inspect its execution timeline, details, and logs.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
