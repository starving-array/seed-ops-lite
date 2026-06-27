import { useState, useEffect, useRef } from 'react'
import {
  Button,
  Card,
  Alert,
  Divider,
  PageHeader,
  Spinner,
  Input,
  Select,
  Checkbox,
  Badge,
} from '../../components/ui'
import { useSchema } from '../../context/SchemaContext'
import { schemaService } from '../../services/schema'
import type { GenerationResponse } from '../../services/schema'
import { useNotifications } from '../../context/NotificationContext'

export const DataGeneration = () => {
  const { tables, relationships, isLoading: isSchemaLoading } = useSchema()
  const { addNotification } = useNotifications()

  // Generation Settings State
  const [globalRowCount, setGlobalRowCount] = useState<number>(100)
  const [batchSize, setBatchSize] = useState<number>(50)
  const [seed, setSeed] = useState<string>('')
  const [outputFormat, setOutputFormat] = useState<string>('json')
  
  // Table-specific row targets and toggle selection
  const [enabledTables, setEnabledTables] = useState<Record<string, boolean>>({})
  const [rowTargets, setRowTargets] = useState<Record<string, number>>({})

  // Schema Validation check on mount
  const [validationPassed, setValidationPassed] = useState<boolean | null>(null)
  const [validationWarningCount, setValidationWarningCount] = useState<number>(0)
  const [isValidatingSchema, setIsValidatingSchema] = useState<boolean>(true)

  // Active run state
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<'idle' | 'queued' | 'running' | 'completed' | 'failed'>('idle')
  const [progressData, setProgressData] = useState<GenerationResponse | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)
  
  // Timer and metrics
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const timerRef = useRef<any>(null)
  const pollingRef = useRef<any>(null)

  // Initialize targets and enabled states from loaded tables
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
          const warningCount = response.data.filter((r) => r.severity === 'Warning').length
          setValidationPassed(!hasErrors)
          setValidationWarningCount(warningCount)
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

  // Actions
  const handleStartGeneration = async () => {
    // 1. Gather enabled row targets
    const activeTargets: Record<string, number> = {}
    let totalTargetRows = 0
    tables.forEach((t) => {
      if (enabledTables[t.name]) {
        activeTargets[t.name] = rowTargets[t.name] || 10
        totalTargetRows += activeTargets[t.name]
      }
    })

    if (totalTargetRows === 0) {
      alert('Please select at least one table to generate data.')
      return
    }

    setRunStatus('queued')
    setElapsedSeconds(0)
    setIsCancelling(false)
    setProgressData(null)

    try {
      const response = await schemaService.startGeneration({
        schemaState: { tables, relationships },
        rowTargets: activeTargets,
        seed: seed ? parseInt(seed, 10) : null,
        batchSize,
        outputFormat,
      })

      if (response.success && response.data) {
        setWorkflowId(response.data.workflowId)
        setProgressData(response.data)
        addNotification({
          type: 'info',
          title: 'Workflow Queued',
          message: 'Topological synthetics generation task successfully scheduled on worker node.',
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
          message: 'Graceful cancellation signal transmitted to worker node.',
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

  const handleDownloadData = () => {
    if (!progressData || !progressData.downloadPlaceholder) return
    
    // Simulate downloading by prompting a success notification and fetching download payload
    addNotification({
      type: 'success',
      title: 'Dataset Downloaded',
      message: `Exported dataset downloaded successfully as ${outputFormat.toUpperCase()}`,
    })
    
    // In a production app, window.open(progressData.downloadPlaceholder) would be used.
    console.log(`Downloading dataset from placeholder: ${progressData.downloadPlaceholder}`)
  }

  const handleReset = () => {
    setRunStatus('idle')
    setWorkflowId(null)
    setProgressData(null)
    setElapsedSeconds(0)
  }

  // Pre-calculations & heuristic previews
  const selectedTablesList = tables.filter((t) => enabledTables[t.name])
  const totalRecordsToGenerate = selectedTablesList.reduce(
    (acc, t) => acc + (rowTargets[t.name] || 0),
    0
  )

  // Heuristics: ~0.02s per record with standard AI models and deterministic strategies mixed
  const estimatedExecutionTime = totalRecordsToGenerate * 0.02
  // Heuristics: ~0.25KB memory per record structured payload
  const estimatedMemoryUsage = (totalRecordsToGenerate * 0.25).toFixed(1)

  // Progress monitoring values
  const activeTableProgress = progressData?.progress.find((p) => p.status === 'Running')
  const totalRowsGenerated = progressData?.totalRowsGenerated || 0
  const completionPercentage = totalRecordsToGenerate > 0 
    ? Math.min(100, Math.round((totalRowsGenerated / totalRecordsToGenerate) * 100))
    : 0

  // Velocity (records/second) and Remaining time estimate
  const generationVelocity = elapsedSeconds > 0 ? (totalRowsGenerated / elapsedSeconds) : 0
  const remainingRecords = totalRecordsToGenerate - totalRowsGenerated
  const estimatedSecondsRemaining = generationVelocity > 0 
    ? Math.max(0, Math.round(remainingRecords / generationVelocity))
    : Math.max(0, Math.round(estimatedExecutionTime - elapsedSeconds))

  if (isSchemaLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Spinner size="lg" />
        <span className="text-sm text-slate-400">Loading schema state registry...</span>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in">
      <PageHeader
        title="Synthetic Data Generation"
        subtitle="Generate mock relational data matching constraints and foreign keys topologically."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ==================== LEFT CONFIG PANEL ==================== */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Main Configuration Card */}
          <Card className="p-6 space-y-6 bg-slate-900/40 border-slate-800/80">
            <div className="flex justify-between items-center border-b border-slate-800/60 pb-3">
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Generation Parameters
              </h2>
              <Badge variant={validationPassed ? 'success' : 'warning'}>
                {validationPassed ? 'Schema Validated' : `Validation Warns (${validationWarningCount})`}
              </Badge>
            </div>

            {runStatus === 'idle' ? (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Input
                    label="Default Rows per Table"
                    id="globalRowCount"
                    type="number"
                    min={1}
                    value={globalRowCount}
                    onChange={(e) => setGlobalRowCount(parseInt(e.target.value, 10) || 10)}
                  />
                  <Input
                    label="Batch Size"
                    id="batchSize"
                    type="number"
                    min={1}
                    value={batchSize}
                    onChange={(e) => setBatchSize(parseInt(e.target.value, 10) || 10)}
                  />
                  <Input
                    label="Random Seed (Optional)"
                    id="seed"
                    type="number"
                    placeholder="e.g. 4242"
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Select
                    label="Output Format (Placeholder)"
                    id="outputFormat"
                    value={outputFormat}
                    onChange={(e) => setOutputFormat(e.target.value)}
                    options={[
                      { value: 'json', label: 'JSON Dataset format' },
                      { value: 'csv', label: 'CSV Tabular format' },
                      { value: 'sql', label: 'SQL Inserts script' },
                    ]}
                  />
                  <div className="flex flex-col justify-end pb-1 text-slate-500 text-xs italic">
                    Note: Output formatting formats belong to subsequent phases.
                  </div>
                </div>

                <Divider label="Configure Row Targets per Table" />

                {tables.length === 0 ? (
                  <Alert variant="warning" title="No Schema Registered">
                    Please navigate to the Schema Designer and create entity tables before configuring generation runs.
                  </Alert>
                ) : (
                  <div className="space-y-3.5 max-h-[300px] overflow-y-auto pr-1">
                    {tables.map((t) => (
                      <div
                        key={t.id}
                        className="flex items-center justify-between gap-4 p-3 bg-slate-950/20 border border-slate-800/80 rounded-xl hover:border-slate-700/60 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <Checkbox
                            label={t.name}
                            id={`enable-${t.name}`}
                            checked={enabledTables[t.name] || false}
                            onChange={(e) =>
                              setEnabledTables((prev) => ({
                                ...prev,
                                [t.name]: e.target.checked,
                              }))
                            }
                          />
                          <span className="text-[10px] bg-slate-800 text-slate-400 py-0.5 px-2 rounded-full font-semibold border border-slate-700/50">
                            {t.columns.length} cols
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
              </div>
            ) : (
              /* Running Dashboard / Execution status monitoring */
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider">
                      Workflow Job Status
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">⚡</span>
                      <h3 className="text-lg font-bold text-white uppercase">
                        {runStatus}
                      </h3>
                    </div>
                  </div>
                  {runStatus === 'running' && (
                    <div className="text-right space-y-1">
                      <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider block">
                        Generation Speed
                      </span>
                      <span className="text-xs text-indigo-400 font-bold">
                        {generationVelocity.toFixed(0)} rec/s
                      </span>
                    </div>
                  )}
                </div>

                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-semibold text-slate-400">
                    <span>Overall Progress</span>
                    <span>{completionPercentage}% ({totalRowsGenerated} / {totalRecordsToGenerate} rows)</span>
                  </div>
                  {activeTableProgress && (
                    <div className="text-xs text-indigo-400 font-semibold animate-pulse">
                      Generating table: <span className="underline">{activeTableProgress.tableName}</span> ({activeTableProgress.rowsGenerated} / {activeTableProgress.targetRows})
                    </div>
                  )}
                  <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800/80">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600 rounded-full transition-all duration-300 shadow-md shadow-indigo-500/20"
                      style={{ width: `${completionPercentage}%` }}
                    />
                  </div>
                </div>

                {/* Dynamic Monitor Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-950/40 rounded-xl border border-slate-850">
                  <div className="text-left space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                      Elapsed Time
                    </span>
                    <p className="text-base font-bold text-slate-200">{elapsedSeconds}s</p>
                  </div>
                  <div className="text-left space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                      Estimated Remaining
                    </span>
                    <p className="text-base font-bold text-slate-200">
                      {runStatus === 'running' ? `${estimatedSecondsRemaining}s` : 'Calculating...'}
                    </p>
                  </div>
                  <div className="text-left space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                      Completed Tables
                    </span>
                    <p className="text-base font-bold text-slate-200">
                      {progressData?.progress.filter(p => p.status === 'Completed').length || 0} / {progressData?.progress.length || 0}
                    </p>
                  </div>
                  <div className="text-left space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                      LLM Tokens Used
                    </span>
                    <p className="text-base font-bold text-indigo-400">
                      {((progressData as any)?.statistics?.total_tokens || 0) || 'N/A'}
                    </p>
                  </div>
                </div>

                {/* Table by Table Progress monitoring list */}
                <div className="space-y-2.5">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Execution Graph Queue
                  </h3>
                  <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                    {progressData?.progress.map((p) => {
                      let statusBadge = (
                        <span className="text-[9px] bg-slate-800 text-slate-400 py-0.5 px-2 rounded-full font-bold">
                          PENDING
                        </span>
                      )
                      if (p.status === 'Running') {
                        statusBadge = (
                          <span className="text-[9px] bg-indigo-500/10 text-indigo-400 py-0.5 px-2 rounded-full font-bold animate-pulse">
                            GENERATING
                          </span>
                        )
                      } else if (p.status === 'Completed') {
                        statusBadge = (
                          <span className="text-[9px] bg-emerald-500/10 text-emerald-400 py-0.5 px-2 rounded-full font-bold">
                            COMPLETED
                          </span>
                        )
                      } else if (p.status === 'Failed') {
                        statusBadge = (
                          <span className="text-[9px] bg-red-500/10 text-red-400 py-0.5 px-2 rounded-full font-bold">
                            FAILED
                          </span>
                        )
                      }

                      return (
                        <div
                          key={p.tableName}
                          className="flex items-center justify-between p-2.5 bg-slate-950/20 border border-slate-850 rounded-xl text-xs"
                        >
                          <div className="flex items-center gap-2 font-semibold text-slate-300">
                            <span>📊</span>
                            <span>{p.tableName}</span>
                          </div>
                          
                          <div className="flex items-center gap-4">
                            <span className="text-slate-400 font-medium">
                              {p.rowsGenerated} / {p.targetRows} rows
                            </span>
                            {statusBadge}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Action Buttons for active running state */}
                <div className="flex items-center gap-3">
                  {(runStatus === 'queued' || runStatus === 'running') && (
                    <Button
                      variant="danger"
                      onClick={handleCancelGeneration}
                      disabled={isCancelling}
                      className="w-full flex items-center justify-center gap-1.5"
                    >
                      {isCancelling ? <Spinner size="sm" /> : '🛑'} Cancel Data Generation
                    </Button>
                  )}
                  {runStatus === 'completed' && (
                    <div className="w-full flex gap-3">
                      <Button
                        variant="primary"
                        onClick={handleDownloadData}
                        className="flex-1 flex items-center justify-center gap-1.5"
                      >
                        💾 Download Dataset
                      </Button>
                      <Button variant="secondary" onClick={handleReset} className="px-5">
                        🔄 Create New Run
                      </Button>
                    </div>
                  )}
                  {runStatus === 'failed' && (
                    <div className="w-full space-y-4">
                      {progressData?.errors && progressData.errors.length > 0 && (
                        <Alert variant="error" title="Critical Exception Halted Seeder">
                          {progressData.errors[0]}
                        </Alert>
                      )}
                      <Button
                        variant="primary"
                        onClick={handleReset}
                        className="w-full flex items-center justify-center gap-1.5"
                      >
                        🔄 Reconfigure Parameters
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* ==================== RIGHT PANEL: PREVIEW & STATS ==================== */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Generation Preview Card */}
          <Card className="p-4 space-y-4 bg-slate-900/40 border-slate-800/80">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Run Configuration Preview
            </h2>
            <Divider />
            <div className="space-y-3.5 text-xs text-left">
              <div className="flex justify-between">
                <span className="text-slate-400">Selected Tables</span>
                <span className="font-semibold text-slate-200">
                  {selectedTablesList.length} / {tables.length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Estimated Records</span>
                <span className="font-semibold text-slate-200">
                  {totalRecordsToGenerate}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Estimated Exec. Time</span>
                <span className="font-semibold text-slate-200 text-indigo-400 font-mono">
                  {estimatedExecutionTime.toFixed(1)}s
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Est. Heap Memory Overhead</span>
                <span className="font-semibold text-slate-200 font-mono">
                  {estimatedMemoryUsage} KB
                </span>
              </div>
            </div>
            
            <Divider label="Integrity Checklist" />
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2 text-slate-300">
                <span className={validationPassed ? 'text-emerald-400' : 'text-slate-500'}>
                  {validationPassed ? '✓' : '○'}
                </span>
                <span>Relational checks parsed</span>
              </div>
              <div className="flex items-center gap-2 text-slate-300">
                <span className={seed ? 'text-indigo-400' : 'text-slate-500'}>
                  {seed ? '✓' : '○'}
                </span>
                <span>Deterministic seed locked</span>
              </div>
            </div>

            {runStatus === 'idle' && (
              <>
                <Divider />
                <Button
                  variant="primary"
                  onClick={handleStartGeneration}
                  disabled={totalRecordsToGenerate === 0}
                  className="w-full flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold"
                >
                  ⚡ Start Synthetic Seeding
                </Button>
              </>
            )}
          </Card>

          {/* Validation Warnings Alert block if warnings exist */}
          {validationPassed === false && !isValidatingSchema && tables.length > 0 && (
            <Alert variant="warning" title="Design Validations Alert">
              The current schema contains design errors. Synthetics generation may fail or skip constraint bindings. Consider running AI validation review.
            </Alert>
          )}
        </div>
      </div>
    </div>
  )
}
