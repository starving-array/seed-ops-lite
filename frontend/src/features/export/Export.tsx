import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Button,
  Card,
  Select,
  Badge,
  Alert,
  Spinner,
} from '../../components/ui'
import { schemaService } from '../../services/schema'
import type { ExportableDataset, ExportSettings, Job } from '../../services/schema'
import { useNotifications } from '../../context/NotificationContext'
import { API_CONFIG } from '../../api/config'

export const Export = () => {
  const [searchParams] = useSearchParams()
  const initialWorkflowId = searchParams.get('workflowId')
  const { addNotification } = useNotifications()
  const [datasets, setDatasets] = useState<ExportableDataset[]>([])
  const [exportJobs, setExportJobs] = useState<Job[]>([])
  const [loadingDatasets, setLoadingDatasets] = useState(true)
  const [loadingJobs, setLoadingJobs] = useState(true)

  // Selection & Configuration State
  const [selectedDataset, setSelectedDataset] = useState<ExportableDataset | null>(null)
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [exportFormat, setExportFormat] = useState<'csv' | 'json' | 'sql'>('json')
  const [singleFile, setSingleFile] = useState(true)
  const [compression, setCompression] = useState(false)
  const [includeMetadata, setIncludeMetadata] = useState(false)
  const [fileNameConvention, setFileNameConvention] = useState<'default' | 'timestamp'>('default')

  const [previewRecords, setPreviewRecords] = useState<Record<string, any[]> | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const loadPreview = async () => {
    if (!selectedDataset) return
    setPreviewLoading(true)
    setShowPreview(true)
    try {
      const res = await schemaService.getPreviewData(selectedDataset.workflowId)
      if (res.success && res.data) {
        setPreviewRecords(res.data)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setPreviewLoading(false)
    }
  }

  const pollingRef = useRef<any>(null)

  // Fetch exportable datasets
  const fetchDatasets = async (showLoading = false) => {
    if (showLoading) setLoadingDatasets(true)
    try {
      const response = await schemaService.listExportableDatasets()
      if (response.success && response.data) {
        setDatasets(response.data)
      }
    } catch (err: any) {
      console.error('Error fetching datasets:', err)
    } finally {
      if (showLoading) setLoadingDatasets(false)
    }
  }

  // Fetch export jobs history
  const fetchExportJobs = useCallback(async (showLoading = false) => {
    if (showLoading) setLoadingJobs(true)
    try {
      const response = await schemaService.listJobs({ job_type: 'export' })
      if (response.success && response.data) {
        setExportJobs(response.data)
      }
    } catch (err: any) {
      console.error('Error fetching export jobs:', err)
    } finally {
      if (showLoading) setLoadingJobs(false)
    }
  }, [])

  // Poll for job updates and dataset list
  useEffect(() => {
    fetchDatasets(true)
    fetchExportJobs(true)

    pollingRef.current = setInterval(() => {
      fetchDatasets(false)
      fetchExportJobs(false)
    }, 3000)

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [fetchExportJobs])

  // Auto-select dataset if initialWorkflowId query param is provided
  useEffect(() => {
    if (initialWorkflowId && datasets.length > 0) {
      const match = datasets.find((d) => d.workflowId === initialWorkflowId)
      if (match) {
        setSelectedDataset(match)
      }
    }
  }, [initialWorkflowId, datasets])

  // Select all tables by default when selected dataset changes
  useEffect(() => {
    if (selectedDataset) {
      const tables = selectedDataset.progress.map((p) => p.tableName)
      setSelectedTables(tables)
    } else {
      setSelectedTables([])
    }
  }, [selectedDataset])

  const handleTableToggle = (tableName: string) => {
    if (selectedTables.includes(tableName)) {
      setSelectedTables(selectedTables.filter((t) => t !== tableName))
    } else {
      setSelectedTables([...selectedTables, tableName])
    }
  }

  // Start Export Job
  const handleStartExport = async () => {
    if (!selectedDataset) return

    const settings: ExportSettings = {
      workflowId: selectedDataset.workflowId,
      format: exportFormat,
      tables: selectedTables,
      singleFile,
      compression,
      includeMetadata,
      fileNameConvention,
    }

    addNotification({
      type: 'info',
      title: 'Export Started',
      message: `Packaging ${selectedTables.length} tables in ${exportFormat.toUpperCase()} format.`,
    })

    try {
      const response = await schemaService.startExport(settings)
      if (response.success && response.data) {
        setSelectedDataset(null) // Reset selection
        fetchExportJobs(false)
      } else {
        addNotification({
          type: 'error',
          title: 'Export Failed',
          message: response.error?.message || 'Failed to queue export job.',
        })
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Network Error',
        message: err.message || 'Request failed.',
      })
    }
  }

  // Cancel Export Job
  const handleCancelExport = async (jobId: string) => {
    try {
      const response = await schemaService.cancelJob(jobId)
      if (response.success) {
        addNotification({
          type: 'warning',
          title: 'Export Aborted',
          message: `Export job ${jobId.slice(0, 8)} was terminated.`,
        })
        fetchExportJobs(false)
      }
    } catch (err: any) {
      console.error(err)
    }
  }

  // Trigger Download
  const handleDownloadFile = (jobId: string, filename: string) => {
    const downloadUrl = `${API_CONFIG.baseUrl}/schema/export/${jobId}/download`
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    addNotification({
      type: 'success',
      title: 'File Downloaded',
      message: `Downloaded ${filename} successfully.`,
    })
  }

  // Formatter helpers
  const formatBytes = (bytes: number) => {
    if (!bytes || isNaN(bytes)) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getStepProgressLabel = (job: Job) => {
    const step = job.details?.step || 'Running'
    switch (step) {
      case 'Preparing':
        return '🔄 Preparing Dataset'
      case 'Exporting':
        return '⚡ Serializing Formats'
      case 'Packaging':
        return '📦 Packaging ZIP Archive'
      case 'Completed':
        return '✅ Complete'
      case 'Failed':
        return '❌ Failed'
      default:
        return '⚙️ Exporting'
    }
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-8 text-left animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white font-sans">Export & Data Delivery</h1>
        <p className="text-sm text-slate-400 mt-2">
          Compile and download relational datasets generated from schemas in JSON, CSV, or SQL scripts.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* ================= LEFT COLUMN: DATASETS BROWSER ================= */}
        <div className="lg:col-span-6 space-y-6">
          <Card className="p-6 bg-slate-900/40 border-slate-850 space-y-4">
            <h3 className="text-base font-bold text-white tracking-wide">Available Datasets</h3>
            <p className="text-xs text-slate-400">
              Select a completed synthetic generation run to configure and compile its dataset files.
            </p>

            {loadingDatasets ? (
              <div className="flex flex-col items-center justify-center p-12 gap-2.5">
                <Spinner size="md" />
                <span className="text-xs text-slate-500">Checking exportable sessions...</span>
              </div>
            ) : datasets.length === 0 ? (
              <div className="p-10 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl">
                <span className="text-3xl block mb-2.5">📊</span>
                <p className="text-xs font-semibold text-slate-400">No Generated Datasets Available</p>
                <p className="text-[10px] text-slate-500 mt-1">
                  Run a data generation workflow first under the Data Generation view.
                </p>
              </div>
            ) : (
              <div className="space-y-3.5 max-h-[360px] overflow-y-auto pr-1">
                {datasets.map((dataset) => {
                  const isSelected = selectedDataset?.workflowId === dataset.workflowId
                  return (
                    <div
                      key={dataset.workflowId}
                      onClick={() => setSelectedDataset(dataset)}
                      className={`
                        p-4 rounded-xl border transition-all cursor-pointer text-left
                        ${
                          isSelected
                            ? 'bg-indigo-950/20 border-indigo-500/50 shadow-md shadow-indigo-500/5'
                            : 'bg-slate-900/30 border-slate-850 hover:border-slate-700/60'
                        }
                      `}
                    >
                      <div className="flex justify-between items-start gap-3">
                        <div className="space-y-1">
                          <span className="text-[9px] bg-slate-800 text-indigo-400 px-2 py-0.5 rounded-full font-bold font-mono border border-slate-700/50">
                            ID: {dataset.workflowId.slice(0, 8)}
                          </span>
                          <h4 className="text-xs font-bold text-slate-200 mt-1">
                            {dataset.resultSummary || 'Generation Completed'}
                          </h4>
                          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-500">
                            <span>📅 {new Date(dataset.finishedAt).toLocaleDateString()}</span>
                            <span>•</span>
                            <span className="font-semibold text-slate-400">
                              🔢 {dataset.totalRowsGenerated} rows
                            </span>
                          </div>
                        </div>
                        <Badge variant="success">Available</Badge>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* Export Configurations panel - only shown if dataset is selected */}
          {selectedDataset && (
            <Card className="p-6 bg-slate-900/40 border-slate-850 space-y-6 animate-slide-up">
              <div className="border-b border-slate-800/60 pb-3 flex justify-between items-center">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Configure Export
                </h3>
                <button
                  onClick={() => setSelectedDataset(null)}
                  className="text-xs text-slate-500 hover:text-slate-300"
                >
                  ✕ Clear selection
                </button>
              </div>

              {/* Table selections */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-400 block">Tables to Include</label>
                <div className="grid grid-cols-2 gap-2 p-3 bg-slate-950/30 border border-slate-850 rounded-xl max-h-[140px] overflow-y-auto">
                  {selectedDataset.progress.map((p) => (
                    <label
                      key={p.tableName}
                      className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-white select-none"
                    >
                      <input
                        type="checkbox"
                        checked={selectedTables.includes(p.tableName)}
                        onChange={() => handleTableToggle(p.tableName)}
                        className="rounded border-slate-800 bg-slate-900 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-slate-900 w-3.5 h-3.5"
                      />
                      <span>{p.tableName} ({p.targetRows} rows)</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Format selection */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-400 block">Export Format</label>
                  <Select
                    id="exportFormat"
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as any)}
                    options={[
                      { value: 'json', label: 'JSON Document' },
                      { value: 'csv', label: 'CSV Spreadsheets' },
                      { value: 'sql', label: 'SQL INSERT Script' },
                    ]}
                    className="py-1"
                  />
                </div>

                {/* File Name Convention */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-400 block">File Naming</label>
                  <Select
                    id="fileName"
                    value={fileNameConvention}
                    onChange={(e) => setFileNameConvention(e.target.value as any)}
                    options={[
                      { value: 'default', label: 'Default (dataset_id)' },
                      { value: 'timestamp', label: 'Timestamp suffix' },
                    ]}
                    className="py-1"
                  />
                </div>
              </div>

              {/* Checkbox configurations */}
              <div className="grid grid-cols-1 gap-2.5 p-3 bg-slate-950/20 border border-slate-850 rounded-xl text-xs">
                <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={singleFile}
                    onChange={(e) => setSingleFile(e.target.checked)}
                    className="rounded border-slate-800 bg-slate-900 text-indigo-500 w-3.5 h-3.5"
                  />
                  <div>
                    <span className="font-semibold block text-slate-300">Single File</span>
                    <span className="text-[10px] text-slate-500 block">
                      Combine all table records into a unified file schema.
                    </span>
                  </div>
                </label>

                <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={compression}
                    onChange={(e) => setCompression(e.target.checked)}
                    className="rounded border-slate-800 bg-slate-900 text-indigo-500 w-3.5 h-3.5"
                  />
                  <div>
                    <span className="font-semibold block text-slate-300">ZIP Compression</span>
                    <span className="text-[10px] text-slate-500 block">
                      Package all resulting assets inside a compressed archive.
                    </span>
                  </div>
                </label>

                <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={includeMetadata}
                    onChange={(e) => setIncludeMetadata(e.target.checked)}
                    className="rounded border-slate-800 bg-slate-900 text-indigo-500 w-3.5 h-3.5"
                  />
                  <div>
                    <span className="font-semibold block text-slate-300">Include Metadata JSON</span>
                    <span className="text-[10px] text-slate-500 block">
                      Embed export statistics and schema configurations.
                    </span>
                  </div>
                </label>
              </div>

              {selectedTables.length === 0 && (
                <Alert variant="warning" title="No Tables Selected">
                  You must select at least one database table to build an export target.
                </Alert>
              )}

              <div className="flex gap-2 text-xs">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadPreview}
                  disabled={!selectedDataset}
                  className="w-1/3 py-2 text-xs font-semibold text-indigo-400 border-indigo-500/20 hover:bg-indigo-500/5"
                >
                  👁️ Preview Data
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartExport}
                  disabled={!selectedDataset}
                  className="w-2/3 py-2 text-xs font-bold uppercase tracking-wider"
                >
                  🚀 Queue Export Task
                </Button>
              </div>

              {/* Collapsible preview section */}
              {showPreview && (
                <div className="mt-4 p-4 border border-slate-800 bg-slate-950/40 rounded-xl space-y-3">
                  <div className="flex justify-between items-center">
                    <h4 className="font-bold text-slate-200 text-xs">Dataset Preview</h4>
                    <button
                      onClick={() => setShowPreview(false)}
                      className="text-slate-500 hover:text-slate-350 text-[11px]"
                    >
                      Hide Preview
                    </button>
                  </div>
                  {previewLoading ? (
                    <div className="flex items-center justify-center p-6 gap-2">
                      <Spinner size="sm" />
                      <span className="text-[11px] text-slate-500 font-sans">Loading preview records...</span>
                    </div>
                  ) : previewRecords ? (
                    <div className="space-y-3 max-h-[250px] overflow-y-auto pr-1">
                      {selectedTables.map((tName) => {
                        const records = previewRecords[tName] || []
                        return (
                          <div key={tName} className="space-y-1">
                            <div className="text-[11px] font-bold text-indigo-400 font-mono">
                              {tName} ({records.length} rows loaded)
                            </div>
                            {records.length === 0 ? (
                              <div className="text-[10px] text-slate-650 pl-2">No records found.</div>
                            ) : (
                              <div className="overflow-x-auto border border-slate-900 rounded bg-slate-950/80 p-2">
                                <table className="w-full text-[10px] font-mono text-slate-400">
                                  <thead>
                                    <tr className="border-b border-slate-800 text-slate-500">
                                      {Object.keys(records[0] || {}).map((k) => (
                                        <th key={k} className="text-left px-1 py-0.5">{k}</th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {records.slice(0, 3).map((r, rIdx) => (
                                      <tr key={rIdx} className="border-b border-slate-900/40 hover:bg-slate-900/20">
                                        {Object.values(r).map((v: any, vIdx) => (
                                          <td key={vIdx} className="px-1 py-0.5 max-w-[120px] truncate" title={String(v)}>
                                            {String(v)}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                    {records.length > 3 && (
                                      <tr>
                                        <td colSpan={Object.keys(records[0] || {}).length} className="text-center text-[9px] text-slate-600 py-1">
                                          ... and {records.length - 3} more rows
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        )
                      })}
                      {selectedTables.length === 0 && (
                        <div className="text-[11px] text-slate-500 text-center py-4">No tables selected to preview.</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-[11px] text-slate-500 text-center">Failed to load preview data.</div>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>

        {/* ================= RIGHT COLUMN: MONITOR & DOWNLOADS ================= */}
        <div className="lg:col-span-6 space-y-6">
          {/* Active Job Progress */}
          <Card className="p-6 bg-slate-900/40 border-slate-850 space-y-4">
            <h3 className="text-base font-bold text-white tracking-wide">Active Export Jobs</h3>
            <p className="text-xs text-slate-400">
              Real-time monitoring of compilation, formatting, and file packing operations.
            </p>

            {loadingJobs ? (
              <div className="flex flex-col items-center justify-center p-8 gap-2.5">
                <Spinner size="md" />
                <span className="text-xs text-slate-500">Retrieving running tasks...</span>
              </div>
            ) : exportJobs.filter((j) => j.status === 'Queued' || j.status === 'Running').length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-6">
                No active export operations running. Configure a dataset and launch a task.
              </p>
            ) : (
              <div className="space-y-4">
                {exportJobs
                  .filter((j) => j.status === 'Queued' || j.status === 'Running')
                  .map((job) => (
                    <div
                      key={job.jobId}
                      className="p-4 bg-slate-950/40 border border-slate-850 rounded-xl space-y-3"
                    >
                      <div className="flex justify-between items-center text-xs">
                        <div className="space-y-0.5">
                          <span className="font-mono text-[10px] text-indigo-400 block font-bold">
                            EXPORT ID: {job.jobId.slice(0, 8)}
                          </span>
                          <span className="text-slate-300 font-semibold">
                            {getStepProgressLabel(job)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge variant="info" className="animate-pulse">
                            {job.status}
                          </Badge>
                          <Button
                            variant="secondary"
                            onClick={() => handleCancelExport(job.jobId)}
                            className="py-0.5 px-2 text-[10px] border-slate-800 text-slate-400 hover:text-white"
                          >
                            🛑 Stop
                          </Button>
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div className="space-y-1">
                        <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden border border-slate-850">
                          <div
                            className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-300"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                          <span>{job.progress}%</span>
                          <span>{job.duration.toFixed(1)}s elapsed</span>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </Card>

          {/* Download History / Archive list */}
          <Card className="p-6 bg-slate-900/40 border-slate-850 space-y-4">
            <h3 className="text-base font-bold text-white tracking-wide font-sans">Export & Download History</h3>
            <p className="text-xs text-slate-400">
              Access completed export tasks to download and verify checksum integrity hashes.
            </p>

            {loadingJobs ? (
              <div className="flex justify-center p-8">
                <Spinner size="md" />
              </div>
            ) : exportJobs.filter((j) => j.status === 'Completed' || j.status === 'Failed').length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-6">
                No historical records of compiled downloads found.
              </p>
            ) : (
              <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                {exportJobs
                  .filter((j) => j.status === 'Completed' || j.status === 'Failed')
                  .map((job) => {
                    const isSuccess = job.status === 'Completed'
                    const detail = job.details || {}
                    return (
                      <div
                        key={job.jobId}
                        className="p-3.5 bg-slate-950/20 border border-slate-850 hover:border-slate-800 rounded-xl space-y-2.5 text-xs text-left"
                      >
                        <div className="flex justify-between items-start gap-2.5">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono font-bold text-[10px] text-slate-400">
                                {job.jobId.slice(0, 8)}
                              </span>
                              <span className="text-[10px] text-slate-600">•</span>
                              <Badge
                                variant={
                                  detail.format === 'csv'
                                    ? 'success'
                                    : detail.format === 'sql'
                                      ? 'warning'
                                      : 'info'
                                }
                                className="py-0 uppercase font-mono text-[9px] font-bold"
                              >
                                {detail.format || 'dataset'}
                              </Badge>
                            </div>
                            <h4 className="font-semibold text-slate-300">
                              📄 {detail.filename || `Dataset_${job.jobId.slice(0, 8)}`}
                            </h4>
                            <p className="text-[10px] text-slate-500">
                              Exported: {new Date(job.finishedAt || job.startedAt).toLocaleString()}
                            </p>
                          </div>

                          <div className="flex flex-col items-end gap-1.5 shrink-0">
                            <span className="text-[10px] font-semibold text-slate-400">
                              {formatBytes(detail.fileSizeBytes)}
                            </span>
                            {isSuccess ? (
                              <Button
                                variant="primary"
                                onClick={() =>
                                  handleDownloadFile(job.jobId, detail.filename || 'dataset')
                                }
                                className="py-1 px-2.5 text-[10px] font-bold"
                              >
                                📥 Download
                              </Button>
                            ) : (
                              <Badge variant="error">Failed</Badge>
                            )}
                          </div>
                        </div>

                        {/* Checksum & Error info */}
                        {isSuccess && detail.checksum && (
                          <div className="bg-slate-950 p-2 rounded-lg border border-slate-900 font-mono text-[9px] text-indigo-300 select-all overflow-x-auto whitespace-nowrap">
                            <span className="text-slate-500 font-bold mr-1">SHA-256:</span>
                            {detail.checksum}
                          </div>
                        )}

                        {!isSuccess && job.errorMessage && (
                          <p className="text-[10px] text-red-400 bg-red-950/10 p-2 rounded-lg border border-red-900/20">
                            ⚠️ {job.errorMessage}
                          </p>
                        )}
                      </div>
                    )
                  })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
