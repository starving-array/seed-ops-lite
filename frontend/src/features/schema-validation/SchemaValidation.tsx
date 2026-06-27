import { useState, useMemo } from 'react'
import {
  Card,
  Badge,
  Divider,
  Grid,
  PageHeader,
} from '../../components/ui'
import { useSchema } from '../../context/SchemaContext'
import type { Table, Relationship } from '../../context/SchemaContext'

interface ValidationResult {
  id: string
  category:
    | 'Tables'
    | 'Columns'
    | 'Relationships'
    | 'Naming'
    | 'Constraints'
    | 'Data Types'
  severity: 'Passed' | 'Info' | 'Warning' | 'Error'
  title: string
  description: string
  suggestedFix: string
}

const RESERVED_KEYWORDS = [
  'select',
  'table',
  'order',
  'group',
  'user',
  'where',
  'join',
  'create',
  'delete',
  'update',
  'insert',
  'from',
  'into',
  'by',
  'index',
  'primary',
  'key',
  'foreign',
  'constraint',
  'null',
]
const IDENTIFIER_REGEX = /^[a-zA-Z_][a-zA-Z0-9_]*$/

const runValidation = (
  tables: Table[],
  relationships: Relationship[]
): ValidationResult[] => {
  const results: ValidationResult[] = []

  // Check Table rules
  const tableNames = new Set<string>()
  tables.forEach((t) => {
    if (!t.name || t.name.trim() === '') {
      results.push({
        id: `table-empty-${t.id}`,
        category: 'Tables',
        severity: 'Error',
        title: 'Empty Table Name',
        description: 'A table is defined with an empty or whitespace name.',
        suggestedFix: 'Rename the table with a valid unique name.',
      })
    } else {
      if (tableNames.has(t.name.toLowerCase())) {
        results.push({
          id: `table-dup-${t.id}`,
          category: 'Tables',
          severity: 'Error',
          title: `Duplicate Table Name: "${t.name}"`,
          description: `Multiple tables are defined with the name "${t.name}". Table names must be unique.`,
          suggestedFix: `Rename this table to avoid naming conflicts.`,
        })
      }
      tableNames.add(t.name.toLowerCase())

      if (!IDENTIFIER_REGEX.test(t.name)) {
        results.push({
          id: `table-naming-invalid-${t.id}`,
          category: 'Naming',
          severity: 'Error',
          title: `Invalid Table Identifier: "${t.name}"`,
          description: `The table name "${t.name}" contains invalid characters. Database table identifiers should only contain letters, numbers, and underscores, and must start with a letter or underscore.`,
          suggestedFix: `Rename the table using snake_case conventions.`,
        })
      }

      if (RESERVED_KEYWORDS.includes(t.name.toLowerCase())) {
        results.push({
          id: `table-naming-keyword-${t.id}`,
          category: 'Naming',
          severity: 'Warning',
          title: `Reserved SQL Keyword used: "${t.name}"`,
          description: `The table name "${t.name}" is a reserved SQL keyword. Using reserved keywords can cause syntactical issues during query compiler executions.`,
          suggestedFix: `Consider renaming the table (e.g. prefixing or suffixing it, like "app_${t.name}").`,
        })
      }

      if (/[A-Z]/.test(t.name)) {
        results.push({
          id: `table-naming-case-${t.id}`,
          category: 'Naming',
          severity: 'Warning',
          title: `Non-standard Case: "${t.name}"`,
          description: `The table name "${t.name}" contains uppercase letters. Database best practices recommend lowercase snake_case formatting.`,
          suggestedFix: `Rename the table to lowercase snake_case (e.g., "${t.name.toLowerCase()}").`,
        })
      }
    }

    if (t.columns.length === 0) {
      results.push({
        id: `table-empty-cols-${t.id}`,
        category: 'Tables',
        severity: 'Error',
        title: `Table "${t.name}" has no columns`,
        description:
          'A table must contain at least one column definition to generate SQL inserts.',
        suggestedFix:
          'Navigate back to the Schema Designer and add at least one column (e.g., a primary key).',
      })
    }

    // Check Column rules
    const colNames = new Set<string>()
    let pkCount = 0
    t.columns.forEach((c) => {
      if (!c.name || c.name.trim() === '') {
        results.push({
          id: `col-empty-${t.id}-${c.id}`,
          category: 'Columns',
          severity: 'Error',
          title: `Empty Column Name in Table "${t.name}"`,
          description:
            'A column in this table is defined with an empty or whitespace name.',
          suggestedFix: 'Specify a valid column name.',
        })
      } else {
        if (colNames.has(c.name.toLowerCase())) {
          results.push({
            id: `col-dup-${t.id}-${c.id}`,
            category: 'Columns',
            severity: 'Error',
            title: `Duplicate Column Name: "${c.name}" in Table "${t.name}"`,
            description: `Table "${t.name}" has multiple columns named "${c.name}". Column names must be unique within a table.`,
            suggestedFix: `Rename the column to avoid conflicts.`,
          })
        }
        colNames.add(c.name.toLowerCase())

        if (!IDENTIFIER_REGEX.test(c.name)) {
          results.push({
            id: `col-naming-invalid-${t.id}-${c.id}`,
            category: 'Naming',
            severity: 'Error',
            title: `Invalid Column Identifier: "${c.name}" in Table "${t.name}"`,
            description: `The column name "${c.name}" in table "${t.name}" contains invalid characters. Column identifiers must be alphanumeric or underscores.`,
            suggestedFix: `Rename the column to use only alphanumeric characters and underscores.`,
          })
        }

        if (RESERVED_KEYWORDS.includes(c.name.toLowerCase())) {
          results.push({
            id: `col-naming-keyword-${t.id}-${c.id}`,
            category: 'Naming',
            severity: 'Warning',
            title: `Reserved SQL Keyword in Column: "${c.name}" in Table "${t.name}"`,
            description: `Column "${c.name}" in table "${t.name}" is a reserved SQL keyword. This might cause compilation warnings on database servers.`,
            suggestedFix: `Consider using a more descriptive column name (e.g. "order_date" instead of "date").`,
          })
        }

        if (/[A-Z]/.test(c.name)) {
          results.push({
            id: `col-naming-case-${t.id}-${c.id}`,
            category: 'Naming',
            severity: 'Warning',
            title: `Non-standard Case: "${c.name}" in Table "${t.name}"`,
            description: `The column name "${c.name}" in table "${t.name}" contains uppercase letters. Lowercase snake_case is highly recommended.`,
            suggestedFix: `Rename the column to lowercase snake_case (e.g., "${c.name.toLowerCase()}").`,
          })
        }
      }

      if (!c.type) {
        results.push({
          id: `col-type-missing-${t.id}-${c.id}`,
          category: 'Data Types',
          severity: 'Error',
          title: `Missing Data Type for Column "${c.name}" in Table "${t.name}"`,
          description:
            'Every column definition must carry an explicit SQL type binding.',
          suggestedFix:
            'Select a valid type (e.g., VARCHAR, INTEGER, TEXT, etc.) from the types dropdown.',
        })
      }

      if (c.isPrimaryKey) {
        pkCount++
      }
    })

    if (pkCount > 1) {
      results.push({
        id: `table-multiple-pk-${t.id}`,
        category: 'Constraints',
        severity: 'Error',
        title: `Multiple Primary Keys in Table "${t.name}"`,
        description: `Table "${t.name}" has ${pkCount} columns configured as Primary Keys. Most relational databases only support a single primary key per table.`,
        suggestedFix:
          'Toggle off primary key settings for duplicate columns, or build a composite constraint.',
      })
    }
  })

  // Check Relationship rules
  const relKeys = new Set<string>()
  relationships.forEach((r) => {
    const sTable = tables.find((t) => t.id === r.sourceTableId)
    const tTable = tables.find((t) => t.id === r.targetTableId)

    if (!r.sourceTableId || !sTable) {
      results.push({
        id: `rel-source-table-missing-${r.id}`,
        category: 'Relationships',
        severity: 'Error',
        title: `Missing Source Table in Relationship "${r.name}"`,
        description:
          'The configured source table reference cannot be found in the current schema design.',
        suggestedFix: 'Re-assign or delete this relationship.',
      })
    }

    if (!r.targetTableId || !tTable) {
      results.push({
        id: `rel-target-table-missing-${r.id}`,
        category: 'Relationships',
        severity: 'Error',
        title: `Missing Target Table in Relationship "${r.name}"`,
        description:
          'The configured target table reference cannot be found in the current schema design.',
        suggestedFix: 'Re-assign or delete this relationship.',
      })
    }

    if (sTable) {
      const sCol = sTable.columns.find((c) => c.id === r.sourceColumnId)
      if (!r.sourceColumnId || !sCol) {
        results.push({
          id: `rel-source-col-missing-${r.id}`,
          category: 'Relationships',
          severity: 'Error',
          title: `Missing Source Column in Relationship "${r.name}"`,
          description: `The referenced source column does not exist in table "${sTable.name}".`,
          suggestedFix: 'Select a valid source column.',
        })
      }
    }

    if (tTable) {
      const tCol = tTable.columns.find((c) => c.id === r.targetColumnId)
      if (!r.targetColumnId || !tCol) {
        results.push({
          id: `rel-target-col-missing-${r.id}`,
          category: 'Relationships',
          severity: 'Error',
          title: `Missing Target Column in Relationship "${r.name}"`,
          description: `The referenced target column does not exist in table "${tTable.name}".`,
          suggestedFix: 'Select a valid target column.',
        })
      }
    }

    if (
      r.sourceTableId &&
      r.targetTableId &&
      r.sourceTableId === r.targetTableId
    ) {
      results.push({
        id: `rel-self-ref-${r.id}`,
        category: 'Relationships',
        severity: 'Warning',
        title: `Self-referencing Relationship: "${r.name}"`,
        description: `Table "${sTable?.name || 'unknown'}" is configured to reference itself. This creates recursive hierarchies.`,
        suggestedFix:
          'Verify this self-reference (like manager_id -> user_id) is intentional.',
      })
    }

    const relKey = `${r.sourceTableId}-${r.sourceColumnId}-${r.targetTableId}-${r.targetColumnId}`
    if (relKeys.has(relKey)) {
      results.push({
        id: `rel-dup-${r.id}`,
        category: 'Relationships',
        severity: 'Error',
        title: `Duplicate Relationship Definition: "${r.name}"`,
        description:
          'Multiple relationships configure the exact same foreign key link points.',
        suggestedFix: 'Delete the duplicate relationship definition.',
      })
    }
    relKeys.add(relKey)
  })

  // If no warnings or errors, return success items
  if (results.length === 0 && tables.length > 0) {
    const categories: Array<
      | 'Tables'
      | 'Columns'
      | 'Relationships'
      | 'Naming'
      | 'Constraints'
      | 'Data Types'
    > = [
      'Tables',
      'Columns',
      'Relationships',
      'Naming',
      'Constraints',
      'Data Types',
    ]
    categories.forEach((cat) => {
      results.push({
        id: `pass-${cat}`,
        category: cat,
        severity: 'Passed',
        title: `${cat} Checks Passed`,
        description: `All validation checks in the ${cat} category compiled successfully.`,
        suggestedFix: 'No fix required.',
      })
    })
  }

  return results
}

export const SchemaValidation = () => {
  const { tables, relationships } = useSchema()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'All' | 'Error' | 'Warning' | 'Passed'>(
    'All'
  )
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  const validationResults = useMemo(() => {
    return runValidation(tables, relationships)
  }, [tables, relationships])

  const totalChecks = validationResults.length
  const errorsCount = validationResults.filter((r) => r.severity === 'Error')
    .length
  const warningsCount = validationResults.filter(
    (r) => r.severity === 'Warning'
  ).length
  const passedCount = validationResults.filter((r) => r.severity === 'Passed')
    .length

  // Calculate dynamic validation score
  const validationScore = useMemo(() => {
    if (tables.length === 0) return 0
    const points = 100 - errorsCount * 15 - warningsCount * 5
    return Math.max(0, points)
  }, [tables.length, errorsCount, warningsCount])

  const filteredResults = useMemo(() => {
    return validationResults.filter((r) => {
      const matchesSearch =
        r.title.toLowerCase().includes(search.toLowerCase()) ||
        r.description.toLowerCase().includes(search.toLowerCase())
      const matchesFilter = filter === 'All' || r.severity === filter
      const matchesCategory =
        selectedCategory === 'all' || r.category === selectedCategory
      return matchesSearch && matchesFilter && matchesCategory
    })
  }, [validationResults, search, filter, selectedCategory])

  const categories = [
    'Tables',
    'Columns',
    'Relationships',
    'Naming',
    'Constraints',
    'Data Types',
  ]

  const severityColors = {
    Error: 'bg-rose-500/10 border-rose-500/20 text-rose-200',
    Warning: 'bg-amber-500/10 border-amber-500/20 text-amber-200',
    Info: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-200',
    Passed: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-200',
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in">
      <PageHeader
        title="Schema Validation Workspace"
        subtitle="Analyze configuration models, foreign constraints, and syntax identifiers."
      />

      {/* Summary Cards */}
      <Grid cols={4} className="gap-6">
        <Card className="p-5 flex flex-col justify-between h-32">
          <span className="text-[10px] font-bold text-slate-500 uppercase">
            Validation Score
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {validationScore}%
            </span>
            <span className="text-[10px] text-slate-500">Live Rating</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-2">
            <div
              className={`h-full transition-all duration-500 ${
                validationScore >= 90
                  ? 'bg-emerald-500'
                  : validationScore >= 70
                    ? 'bg-amber-500'
                    : 'bg-rose-500'
              }`}
              style={{ width: `${validationScore}%` }}
            />
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between h-32">
          <span className="text-[10px] font-bold text-slate-500 uppercase">
            Failed Checks
          </span>
          <div className="text-3xl font-extrabold text-rose-400 tracking-tight">
            {errorsCount}
          </div>
          <span className="text-xs text-slate-500">Critical Blockers</span>
        </Card>

        <Card className="p-5 flex flex-col justify-between h-32">
          <span className="text-[10px] font-bold text-slate-500 uppercase">
            Design Warnings
          </span>
          <div className="text-3xl font-extrabold text-amber-400 tracking-tight">
            {warningsCount}
          </div>
          <span className="text-xs text-slate-500">Optimizations Suggested</span>
        </Card>

        <Card className="p-5 flex flex-col justify-between h-32">
          <span className="text-[10px] font-bold text-slate-500 uppercase">
            Passed Checks
          </span>
          <div className="text-3xl font-extrabold text-emerald-400 tracking-tight">
            {passedCount}
          </div>
          <span className="text-xs text-slate-500">Diagnostic Pass Rate</span>
        </Card>
      </Grid>

      {/* Main Validation Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left categories navigation sidebar */}
        <Card className="lg:col-span-3 p-4 flex flex-col gap-3 bg-slate-900/40 border-slate-800/80">
          <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Validation Categories
          </h2>
          <Divider />
          <button
            onClick={() => setSelectedCategory('all')}
            className={`
              w-full flex items-center justify-between p-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all border text-left
              ${
                selectedCategory === 'all'
                  ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                  : 'bg-slate-900/30 text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
              }
            `}
          >
            <span>All Categories</span>
            <Badge variant="info">{totalChecks}</Badge>
          </button>

          {categories.map((cat) => {
            const catResults = validationResults.filter(
              (r) => r.category === cat
            )
            const catErrors = catResults.filter((r) => r.severity === 'Error')
              .length
            const catWarnings = catResults.filter(
              (r) => r.severity === 'Warning'
            ).length

            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`
                  w-full flex items-center justify-between p-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all border text-left
                  ${
                    selectedCategory === cat
                      ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                      : 'bg-slate-900/30 text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
                  }
                `}
              >
                <span>{cat}</span>
                <div className="flex gap-1.5">
                  {catErrors > 0 && <Badge variant="error">{catErrors}</Badge>}
                  {catWarnings > 0 && (
                    <Badge variant="warning">{catWarnings}</Badge>
                  )}
                  {catErrors === 0 && catWarnings === 0 && (
                    <Badge variant="success">✓</Badge>
                  )}
                </div>
              </button>
            )
          })}
        </Card>

        {/* Center / Right Results List */}
        <div className="lg:col-span-9 space-y-4">
          {/* Filtering & Toolbar */}
          <Card className="p-4 flex flex-col md:flex-row gap-4 justify-between items-center bg-slate-900/60 border-slate-800/80">
            <div className="w-full md:w-72">
              <input
                type="text"
                placeholder="Search validation checks..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
              />
            </div>
            <div className="flex gap-2 w-full md:w-auto overflow-x-auto">
              {(['All', 'Error', 'Warning', 'Passed'] as const).map((sev) => (
                <button
                  key={sev}
                  onClick={() => setFilter(sev)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer whitespace-nowrap ${
                    filter === sev
                      ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
                  }`}
                >
                  {sev === 'All' ? 'All Severities' : `${sev}s`}
                </button>
              ))}
            </div>
          </Card>

          {/* Validation Checklist Cards */}
          <div className="space-y-3">
            {filteredResults.length === 0 ? (
              <div className="text-center py-12 bg-slate-900/20 border border-slate-800/80 rounded-2xl text-slate-500 text-xs">
                No validation checks matched your filter. Select another filter
                above.
              </div>
            ) : (
              filteredResults.map((r) => (
                <div
                  key={r.id}
                  className={`border rounded-xl p-4 flex flex-col gap-2.5 transition-colors ${
                    severityColors[r.severity]
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            r.severity === 'Error'
                              ? 'error'
                              : r.severity === 'Warning'
                                ? 'warning'
                                : r.severity === 'Passed'
                                  ? 'success'
                                  : 'info'
                          }
                          className="uppercase text-[9px] tracking-wider py-0.5 px-1.5 font-bold"
                        >
                          {r.severity}
                        </Badge>
                        <span className="text-[10px] text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded-md border border-slate-700/40">
                          {r.category}
                        </span>
                      </div>
                      <h3 className="font-bold text-sm tracking-tight text-white mt-1">
                        {r.title}
                      </h3>
                    </div>
                  </div>

                  <p className="text-slate-400 text-xs leading-relaxed">
                    {r.description}
                  </p>

                  <div className="text-xs border-t border-slate-800/40 pt-2.5 flex flex-col gap-1">
                    <span className="font-semibold text-slate-300">
                      Suggested Fix:
                    </span>
                    <span className="text-slate-400 italic">
                      {r.suggestedFix}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
