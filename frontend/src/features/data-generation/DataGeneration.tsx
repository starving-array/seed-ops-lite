import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Alert,
  Divider,
  PageHeader,
  Spinner,
  Input,
  Checkbox,
} from '../../components/ui'
import { useSchema } from '../../context/SchemaContext'
import { schemaService } from '../../services/schema'
import type { GenerationResponse } from '../../services/schema'
import { useNotifications } from '../../context/NotificationContext'

export const DataGeneration = () => {
  const { tables, relationships, isLoading: isSchemaLoading, saveStatus } = useSchema()
  const { addNotification } = useNotifications()
  const navigate = useNavigate()

  // Generation Mode: 'quick' | 'advanced'
  const [generationMode, setGenerationMode] = useState<'quick' | 'advanced'>('quick')

  // Quick Generate State
  const [quickSize, setQuickSize] = useState<number>(100)

  // Advanced Generate State
  const [globalRowCount, setGlobalRowCount] = useState<number>(100)
  const [enabledTables, setEnabledTables] = useState<Record<string, boolean>>({})
  const [rowTargets, setRowTargets] = useState<Record<string, number>>({})

  // Schema Validation check on mount
  const [validationPassed, setValidationPassed] = useState<boolean | null>(null)
  const [isValidatingSchema, setIsValidatingSchema] = useState<boolean>(true)

  // Summary and Run confirmation State
  const [showSummary, setShowSummary] = useState(false)

  // Active run state
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<'idle' | 'queued' | 'running' | 'completed' | 'failed'>('idle')
  const [progressData, setProgressData] = useState<GenerationResponse | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)

  // Dataset Preview Modal State
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewRecords, setPreviewRecords] = useState<Record<string, any[]> | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewActiveTable, setPreviewActiveTable] = useState<string>('')

  // Timer and metrics
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const timerRef = useRef<any>(null)
  const pollingRef = useRef<any>(null)

  // Initialize targets and enabled states from loaded tables for Advanced mode
  useEffect(() => {
    if (tables.length > 0) {
      const initialEnabled: Record<string, boolean> = {}
      const initialTargets: Record<string, number> = {}
      tables.forEach((t) => {
        initialEnabled[t.name] = true
        initialTargets[t.name] = globalRowCount
      })
      setEnabledTables(initialEnabled)
      setRowTargets(initialTargets)
    }
  }, [tables, globalRowCount])

  // Perform schema validation check on mount/update
  useEffect(() => {
    const checkValidation = async () => {
      if (tables.length === 0) {
        setIsValidatingSchema(false)
        return
      }
      try {
        setIsValidatingSchema(true)
        const response = await schemaService.validateSchema({ tables, relationships })
        if (response.success && response.data) {
          const hasErrors = response.data.some((r) => r.severity === 'Error')
          setValidationPassed(!hasErrors)
        } else {
          setValidationPassed(false)
        }
      } catch {
        setValidationPassed(false)
      } finally {
        setIsValidatingSchema(false)
      }
    }
    checkValidation()
  }, [tables, relationships])

  // Elapsed Time Counter Effect
  useEffect(() => {
    if (runStatus === 'running') {
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [runStatus])

  // Polling Status Effect
  useEffect(() => {
    if (workflowId && (runStatus === 'queued' || runStatus === 'running')) {
      const pollStatus = async () => {
        try {
          const response = await schemaService.getGenerationStatus(workflowId)
          if (response.success && response.data) {
            const data = response.data
            setProgressData(data)

            const lowerStatus = data.status.toLowerCase()
            if (lowerStatus === 'completed') {
              setRunStatus('completed')
              addNotification({
                type: 'success',
                title: 'Data Generation Complete',
                message: `Successfully generated ${data.totalRowsGenerated} rows across ${data.progress.length} tables in ${(data.durationMs / 1000).toFixed(1)}s.`,
              })
              if (pollingRef.current) clearInterval(pollingRef.current)
            } else if (lowerStatus === 'failed') {
              setRunStatus('failed')
              addNotification({
                type: 'error',
                title: 'Generation Failed',
                message: data.errors[0] || 'The synthetic seeding workflow encountered a critical failure.',
              })
              if (pollingRef.current) clearInterval(pollingRef.current)
            } else if (lowerStatus === 'running') {
              setRunStatus('running')
            }
          }
        } catch (err: any) {
          setRunStatus('failed')
          addNotification({
            type: 'error',
            title: 'Connection Lost',
            message: err.message || 'Lost connection to generation status service.',
          })
          if (pollingRef.current) clearInterval(pollingRef.current)
        }
      }

      // Initial check
      pollStatus()
      pollingRef.current = setInterval(pollStatus, 1000)
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [workflowId, runStatus, addNotification])

  // Fetch preview records when preview modal is toggled open
  useEffect(() => {
    if (showPreviewModal && workflowId && !previewRecords) {
      setPreviewLoading(true)
      schemaService
        .getPreviewData(workflowId)
        .then((res) => {
          if (res.success && res.data) {
            setPreviewRecords(res.data)
            const firstTable = Object.keys(res.data)[0]
            if (firstTable) setPreviewActiveTable(firstTable)
          }
        })
        .catch((err) => {
          console.error('Error fetching preview:', err)
          addNotification({
            type: 'error',
            title: 'Preview Load Failed',
            message: 'Could not fetch generated data records.',
          })
        })
        .finally(() => {
          setPreviewLoading(false)
        })
    }
  }, [showPreviewModal, workflowId, previewRecords, addNotification])

  // Smart allocation of row counts for Quick Generate mode
  const determineQuickRowTargets = (totalSize: number) => {
    const targets: Record<string, number> = {}
    const referencedTableIds = new Set(relationships.map((r) => r.targetTableId))
    const referencedTableNames = new Set(
      tables.filter((t) => referencedTableIds.has(t.id)).map((t) => t.name)
    )

    tables.forEach((t) => {
      if (referencedTableNames.has(t.name)) {
        // Referenced/lookup tables: subset of rows to keep cardinality realistic
        targets[t.name] = Math.max(10, Math.floor(totalSize / 4))
      } else {
        targets[t.name] = totalSize
      }
    })
    return targets
  }

  // Pre-calculations & heuristic previews
  const getActiveTargets = () => {
    if (generationMode === 'quick') {
      return determineQuickRowTargets(quickSize)
    } else {
      const activeTargets: Record<string, number> = {}
      tables.forEach((t) => {
        if (enabledTables[t.name]) {
          activeTargets[t.name] = rowTargets[t.name] || 10
        }
      })
      return activeTargets
    }
  }

  const activeTargets = getActiveTargets()
  const totalRecordsToGenerate = Object.values(activeTargets).reduce((a, b) => a + b, 0)
  const activeTablesCount = Object.keys(activeTargets).length

  // Heuristics: ~0.0004s per record with standard AI models and deterministic strategies mixed
  const estimatedExecutionTime = Math.max(1, Math.ceil(totalRecordsToGenerate * 0.0004 + tables.length * 0.4))
  const memoryUsageText = totalRecordsToGenerate < 1000 ? 'Low' : totalRecordsToGenerate <= 10000 ? 'Medium' : 'High'

  const handleOpenSummary = () => {
    if (saveStatus === 'failed') {
      alert('Cannot generate data: The latest schema updates failed to save. Please return to the Schema Designer and resolve any save errors.')
      return
    }
    if (totalRecordsToGenerate === 0) {
      alert('Please select at least one table and target row count.')
      return
    }
    setShowSummary(true)
  }

  const handleStartGeneration = async () => {
    setShowSummary(false)
    setRunStatus('queued')
    setElapsedSeconds(0)
    setIsCancelling(false)
    setProgressData(null)
    setPreviewRecords(null)

    try {
      const response = await schemaService.startGeneration({
        schemaState: { tables, relationships },
        rowTargets: activeTargets,
        outputFormat: 'json', // Internally defaults to JSON
      })

      if (response.success && response.data) {
        setWorkflowId(response.data.workflowId)
        setProgressData(response.data)
        addNotification({
          type: 'info',
          title: 'Generation Initiated',
          message: 'Data generation task successfully scheduled and started.',
        })
      } else {
        setRunStatus('failed')
        addNotification({
          type: 'error',
          title: 'Scheduling Failed',
          message: response.error?.message || 'Could not queue workflow execution plan.',
        })
      }
    } catch (err: any) {
      setRunStatus('failed')
      addNotification({
        type: 'error',
        title: 'API Call Error',
        message: err.message || 'Failed to initiate synthetic generation request.',
      })
    }
  }

  const handleCancelGeneration = async () => {
    if (!workflowId) return
    setIsCancelling(true)
    try {
      const response = await schemaService.cancelGeneration(workflowId)
      if (response.success) {
        addNotification({
          type: 'warning',
          title: 'Cancellation Sent',
          message: 'Cancellation signal transmitted successfully.',
        })
      } else {
        addNotification({
          type: 'error',
          title: 'Cancellation Failed',
          message: response.error?.message || 'Failed to send cancellation signal.',
        })
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'API Call Error',
        message: err.message || 'Failed to cancel the active generation run.',
      })
    } finally {
      setIsCancelling(false)
    }
  }

  const handleReset = () => {
    setRunStatus('idle')
    setWorkflowId(null)
    setProgressData(null)
    setElapsedSeconds(0)
    setShowSummary(false)
    setShowPreviewModal(false)
    setPreviewRecords(null)
  }

  // Progress monitoring values
  const activeTableProgress = progressData?.progress.find((p) => p.status === 'Running')
  const totalRowsGenerated = progressData?.totalRowsGenerated || 0
  const completionPercentage = totalRecordsToGenerate > 0
    ? Math.min(100, Math.round((totalRowsGenerated / totalRecordsToGenerate) * 100))
    : 0

  // Velocity (records/second) and Remaining time estimate
  const generationVelocity = elapsedSeconds > 0 ? totalRowsGenerated / elapsedSeconds : 0
  const remainingRecords = totalRecordsToGenerate - totalRowsGenerated
  const estimatedSecondsRemaining = generationVelocity > 0
    ? Math.max(0, Math.round(remainingRecords / generationVelocity))
    : Math.max(0, Math.round(estimatedExecutionTime - elapsedSeconds))

  if (isSchemaLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Spinner size="lg" />
        <span className="text-sm text-slate-400 font-sans">Loading schema configuration...</span>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in font-sans">
      <PageHeader
        title="Mock Data Generator"
        subtitle="Produce realistic, relational datasets automatically populated using topological order."
      />

      {/* ==================== 1. PREVIEW PREVIEW MODAL ==================== */}
      {showPreviewModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 flex justify-between items-center">
              <div className="space-y-0.5">
                <h3 className="text-lg font-bold text-white">Generated Dataset Preview</h3>
                <p className="text-xs text-slate-400">Reviewing sample entries from generated tables</p>
              </div>
              <button
                onClick={() => setShowPreviewModal(false)}
                className="text-slate-400 hover:text-white transition-colors p-1 text-lg"
              >
                ✕
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {previewLoading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3">
                  <Spinner size="md" />
                  <span className="text-sm text-slate-400">Loading dataset preview records...</span>
                </div>
              ) : previewRecords ? (
                <div className="space-y-4">
                  {/* Table Selection Tabs */}
                  <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
                    {Object.keys(previewRecords).map((tName) => (
                      <button
                        key={tName}
                        onClick={() => setPreviewActiveTable(tName)}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
                          previewActiveTable === tName
                            ? 'bg-indigo-600/10 border-indigo-500/50 text-indigo-400 font-bold'
                            : 'bg-slate-950/30 border-slate-850 text-slate-400 hover:border-slate-800 hover:text-slate-200'
                        }`}
                      >
                        {tName}
                      </button>
                    ))}
                  </div>

                  {/* Render Table Data */}
                  {previewActiveTable && previewRecords[previewActiveTable] ? (
                    <div className="overflow-x-auto border border-slate-800/80 rounded-xl bg-slate-950/20">
                      {previewRecords[previewActiveTable].length === 0 ? (
                        <div className="p-8 text-center text-slate-500 text-xs">
                          No records generated for table {previewActiveTable}
                        </div>
                      ) : (
                        <table className="w-full text-xs text-left border-collapse">
                          <thead>
                            <tr className="bg-slate-900 border-b border-slate-800 text-slate-300 font-semibold">
                              {Object.keys(previewRecords[previewActiveTable][0]).map((col) => (
                                <th key={col} className="p-3 font-mono">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {previewRecords[previewActiveTable].slice(0, 10).map((row, idx) => (
                              <tr
                                key={idx}
                                className="border-b border-slate-850 hover:bg-slate-900/20 text-slate-400"
                              >
                                {Object.values(row).map((val: any, colIdx) => (
                                  <td key={colIdx} className="p-3 max-w-[200px] truncate font-mono">
                                    {typeof val === 'boolean'
                                      ? val
                                        ? 'True'
                                        : 'False'
                                      : val === null || val === undefined
                                      ? 'null'
                                      : String(val)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500 text-sm">
                  Failed to load dataset records.
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-950/30 border-t border-slate-800 flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setShowPreviewModal(false)}>
                Close Preview
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  setShowPreviewModal(false)
                  if (workflowId) navigate(`/export?workflowId=${workflowId}`)
                }}
              >
                📥 Proceed to Export
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== 2. SUMMARY / CONFIRMATION STEP ==================== */}
      {showSummary && (
        <div className="max-w-xl mx-auto">
          <Card className="p-6 space-y-6 bg-slate-900/40 border-slate-800/80 shadow-xl">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-lg font-bold text-white tracking-wide">Generation Summary</h2>
              <p className="text-xs text-slate-400 mt-1">
                Please confirm the configuration before starting the workflow.
              </p>
            </div>

            <div className="space-y-4 py-2 text-sm text-left">
              <div className="flex justify-between border-b border-slate-850 pb-2">
                <span className="text-slate-400 font-semibold">Active Tables</span>
                <span className="font-bold text-slate-200">{activeTablesCount}</span>
              </div>
              <div className="flex justify-between border-b border-slate-850 pb-2">
                <span className="text-slate-400 font-semibold">Total Estimated Records</span>
                <span className="font-bold text-slate-200">{totalRecordsToGenerate.toLocaleString()}</span>
              </div>
              <div className="flex justify-between border-b border-slate-850 pb-2">
                <span className="text-slate-400 font-semibold">Relational Checks</span>
                <span className="font-bold text-slate-200">{relationships.length} relationships</span>
              </div>
              <div className="flex justify-between border-b border-slate-850 pb-2">
                <span className="text-slate-400 font-semibold">Estimated Time</span>
                <span className="font-bold text-indigo-400">~{estimatedExecutionTime} seconds</span>
              </div>
              <div className="flex justify-between border-b border-slate-850 pb-2">
                <span className="text-slate-400 font-semibold">Estimated Memory Overhead</span>
                <span className={`font-bold ${
                  memoryUsageText === 'Low'
                    ? 'text-emerald-400'
                    : memoryUsageText === 'Medium'
                    ? 'text-amber-400'
                    : 'text-red-400'
                }`}>
                  {memoryUsageText}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-semibold">Generation Strategy</span>
                <span className="font-bold text-slate-200">Automatic</span>
              </div>
            </div>

            <div className="flex gap-4">
              <Button variant="secondary" className="flex-1" onClick={() => setShowSummary(false)}>
                Cancel
              </Button>
              <Button variant="primary" className="flex-1" onClick={handleStartGeneration}>
                Start Generating
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* ==================== 3. CONFIGURATION MODE (IDLE STATE) ==================== */}
      {runStatus === 'idle' && !showSummary && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8 space-y-6">
            {/* Mode selection tabs */}
            <div className="flex gap-2 p-1 bg-slate-950/40 rounded-xl border border-slate-850">
              <button
                onClick={() => setGenerationMode('quick')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                  generationMode === 'quick'
                    ? 'bg-slate-900 text-white shadow-sm border border-slate-800'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚡ Quick Generate
              </button>
              <button
                onClick={() => setGenerationMode('advanced')}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                  generationMode === 'advanced'
                    ? 'bg-slate-900 text-white shadow-sm border border-slate-800'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚙ Advanced Settings
              </button>
            </div>

            <Card className="p-6 space-y-6 bg-slate-900/40 border-slate-800/80">
              {saveStatus === 'failed' && (
                <Alert variant="error" title="Schema Save Failed">
                  Your latest schema changes could not be saved to the database. Data generation is disabled until this is resolved. Return to the Schema Designer and click 'Retry Save'.
                </Alert>
              )}
              {generationMode === 'quick' ? (
                /* QUICK GENERATE SCREEN */
                <div className="space-y-6 text-left">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Select Dataset Size
                    </label>
                    <p className="text-xs text-slate-400">
                      Choose the total size of your mock dataset. Referenced lookup tables are auto-scaled.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[100, 1000, 10000, 100000].map((size) => (
                      <button
                        key={size}
                        onClick={() => setQuickSize(size)}
                        className={`p-4 rounded-xl border transition-all flex flex-col items-center gap-1 hover:border-slate-700 ${
                          quickSize === size
                            ? 'bg-indigo-600/10 border-indigo-500/50 text-white shadow-lg'
                            : 'bg-slate-950/20 border-slate-850 text-slate-400'
                        }`}
                      >
                        <span className="text-base font-bold font-mono">
                          {size.toLocaleString()}
                        </span>
                        <span className="text-[10px] text-slate-500 font-medium">records</span>
                      </button>
                    ))}
                  </div>

                  <div className="pt-4 border-t border-slate-850">
                    <Button
                      variant="primary"
                      onClick={handleOpenSummary}
                      disabled={tables.length === 0 || saveStatus === 'failed'}
                      className="w-full py-3 flex items-center justify-center gap-2 text-sm font-bold shadow-md shadow-indigo-600/10"
                    >
                      ⚡ Start Mock Seeding
                    </Button>
                  </div>
                </div>
              ) : (
                /* ADVANCED GENERATE SCREEN */
                <div className="space-y-6 text-left">
                  <div className="grid grid-cols-1 gap-4">
                    <Input
                      label="Default Row Count"
                      id="globalRowCount"
                      type="number"
                      min={1}
                      value={globalRowCount}
                      onChange={(e) => setGlobalRowCount(parseInt(e.target.value, 10) || 10)}
                    />
                  </div>

                  <Divider label="Row Targets Per Table" />

                  {tables.length === 0 ? (
                    <Alert variant="warning" title="No Schema Registered">
                      Please navigate to the Schema Designer and create tables before generating mock data.
                    </Alert>
                  ) : (
                    <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                      {tables.map((t) => (
                        <div
                          key={t.id}
                          className="flex items-center justify-between gap-4 p-3 bg-slate-950/20 border border-slate-850 rounded-xl hover:border-slate-800 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <Checkbox
                              label={t.name}
                              id={`enable-${t.name}`}
                              checked={enabledTables[t.name] ?? false}
                              onChange={(e) =>
                                setEnabledTables((prev) => ({
                                  ...prev,
                                  [t.name]: e.target.checked,
                                }))
                              }
                            />
                            <span className="text-[9px] bg-slate-800 text-slate-400 py-0.5 px-2 rounded-full font-bold">
                              {t.columns.length} columns
                            </span>
                          </div>

                          <div className="w-28 shrink-0">
                            <Input
                              type="number"
                              min={1}
                              disabled={!enabledTables[t.name]}
                              value={rowTargets[t.name] ?? globalRowCount}
                              onChange={(e) => {
                                const val = parseInt(e.target.value, 10) || 10
                                setRowTargets((prev) => ({
                                  ...prev,
                                  [t.name]: val,
                                }))
                              }}
                              className="h-8 py-1.5"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="pt-4 border-t border-slate-850">
                    <Button
                      variant="primary"
                      onClick={handleOpenSummary}
                      disabled={totalRecordsToGenerate === 0 || saveStatus === 'failed'}
                      className="w-full py-3 flex items-center justify-center gap-2 text-sm font-bold"
                    >
                      ⚡ Apply & Start Seeding
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          </div>

          {/* Validation Warnings Alert block if warnings exist */}
          <div className="lg:col-span-4 space-y-6">
            <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Integrity Checklist
              </h2>
              <Divider />
              <div className="space-y-3.5 text-xs text-left">
                <div className="flex items-center gap-2 text-slate-300">
                  <span className={validationPassed ? 'text-emerald-400' : 'text-slate-500'}>
                    {validationPassed ? '✓' : '○'}
                  </span>
                  <span>Relational configuration checks passed</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <span className="text-indigo-400 font-bold">✓</span>
                  <span>Auto-scaled relationship dependencies active</span>
                </div>
              </div>
            </Card>

            {validationPassed === false && !isValidatingSchema && tables.length > 0 && (
              <Alert variant="warning" title="Design Warnings Active">
                The current schema has validation warnings. Data generation will run but foreign key bounds may skip failed relationships.
              </Alert>
            )}
          </div>
        </div>
      )}

      {/* ==================== 4. RUNNING PROGRESS VIEW ==================== */}
      {(runStatus === 'queued' || runStatus === 'running') && (
        <div className="max-w-2xl mx-auto space-y-6">
          <Card className="p-6 space-y-6 bg-slate-900/40 border-slate-800/80 text-left shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="space-y-1">
                <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider block">
                  Workflow Execution Stage
                </span>
                <h3 className="text-sm font-bold text-indigo-400">
                  {runStatus === 'queued'
                    ? 'Topological Seeding Planning...'
                    : 'Generating Synthetic Records...'}
                </h3>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-950/30 border border-slate-850 px-3 py-1.5 rounded-xl font-mono">
                <span>⏱</span>
                <span>Elapsed: {elapsedSeconds}s</span>
              </div>
            </div>

            {/* Overall Progress Bar */}
            <div className="space-y-3">
              <div className="flex justify-between text-xs font-semibold text-slate-400">
                <span>Overall Progress</span>
                <span className="font-mono">
                  {completionPercentage}% ({totalRowsGenerated.toLocaleString()} /{' '}
                  {totalRecordsToGenerate.toLocaleString()} rows)
                </span>
              </div>
              <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-850">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600 rounded-full transition-all duration-300"
                  style={{ width: `${completionPercentage}%` }}
                />
              </div>
            </div>

            {/* Current generating target details */}
            <div className="p-4 bg-slate-950/20 border border-slate-850 rounded-xl space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Current Table:</span>
                <span className="font-semibold text-slate-200">
                  {activeTableProgress?.tableName || 'Preparing workflow task...'}
                </span>
              </div>
              {activeTableProgress && (
                <div className="flex justify-between text-slate-400">
                  <span>Current Table Progress:</span>
                  <span className="font-semibold text-slate-200 font-mono">
                    {activeTableProgress.rowsGenerated} / {activeTableProgress.targetRows} rows
                  </span>
                </div>
              )}
              <div className="flex justify-between text-slate-400">
                <span>Estimated Remaining Time:</span>
                <span className="font-semibold text-indigo-400 font-mono">
                  {runStatus === 'running' ? `~${estimatedSecondsRemaining} seconds` : 'Calculating...'}
                </span>
              </div>
            </div>

            {/* Cancel Button */}
            <Button
              variant="danger"
              onClick={handleCancelGeneration}
              disabled={isCancelling}
              className="w-full py-3 flex items-center justify-center gap-2 font-bold"
            >
              {isCancelling ? <Spinner size="sm" /> : '🛑'} Cancel Data Generation
            </Button>
          </Card>
        </div>
      )}

      {/* ==================== 5. COMPLETION SCREEN ==================== */}
      {runStatus === 'completed' && (
        <div className="max-w-2xl mx-auto">
          <Card className="p-8 text-center space-y-6 bg-slate-900/40 border-slate-800/80 shadow-2xl">
            {/* Success Icon */}
            <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto text-3xl">
              ✓
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-white tracking-wide">Generation Complete</h2>
              <p className="text-sm text-slate-400">
                Synthetic dataset generated successfully using configured settings.
              </p>
            </div>

            {/* Metrics Panel */}
            <div className="grid grid-cols-3 gap-4 p-4 bg-slate-950/30 border border-slate-850 rounded-2xl text-left">
              <div className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Rows Generated
                </span>
                <p className="text-lg font-bold text-slate-200 font-mono">
                  {totalRowsGenerated.toLocaleString()}
                </p>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Duration
                </span>
                <p className="text-lg font-bold text-slate-200 font-mono">
                  {(progressData?.durationMs ? progressData.durationMs / 1000 : elapsedSeconds).toFixed(1)}s
                </p>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Tables Seeded
                </span>
                <p className="text-lg font-bold text-slate-200 font-mono">
                  {progressData?.progress.filter((p) => p.status === 'Completed').length || 0}
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-4">
              <Button
                variant="secondary"
                className="py-3 font-semibold flex items-center justify-center gap-2"
                onClick={() => setShowPreviewModal(true)}
              >
                👁 Preview Dataset
              </Button>
              <Button
                variant="primary"
                className="py-3 font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/10"
                onClick={() => {
                  if (workflowId) navigate(`/export?workflowId=${workflowId}`)
                }}
              >
                📥 Export Dataset
              </Button>
              <Button
                variant="secondary"
                className="col-span-2 py-2.5 text-xs text-slate-400 font-semibold"
                onClick={handleReset}
              >
                🔄 Generate Again
              </Button>
              <Button
                variant="secondary"
                className="col-span-2 py-2.5 text-xs text-slate-400 font-semibold"
                onClick={() => navigate('/')}
              >
                🏠 Return to Dashboard
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* ==================== 6. FAILED SCREEN ==================== */}
      {runStatus === 'failed' && (
        <div className="max-w-2xl mx-auto">
          <Card className="p-8 text-center space-y-6 bg-slate-900/40 border-slate-800/80 shadow-2xl">
            <div className="w-16 h-16 bg-red-500/10 border border-red-500/30 rounded-full flex items-center justify-center mx-auto text-3xl">
              ✕
            </div>

            <div className="space-y-2">
              <h2 className="text-xl font-bold text-white">Generation Failed</h2>
              <p className="text-sm text-slate-400">
                The synthetic data seeding process encountered an error and halted.
              </p>
            </div>

            {progressData?.errors && progressData.errors.length > 0 && (
              <Alert variant="error" title="Workflow Exception Detail">
                {progressData.errors[0]}
              </Alert>
            )}

            <Button
              variant="primary"
              onClick={handleReset}
              className="w-full py-3 flex items-center justify-center gap-2 font-bold"
            >
              🔄 Reconfigure Parameters
            </Button>
          </Card>
        </div>
      )}
    </div>
  )
}
