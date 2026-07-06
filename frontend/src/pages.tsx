import {
  Button,
  Card,
  Badge,
  Alert,
  Divider,
  Stack,
  Grid,
  PageHeader,
  Spinner,
} from './components/ui'

// Re-export modular pages from feature folders
export { Dashboard } from './features/dashboard/Dashboard'
export { Projects } from './features/projects/Projects'
export { SchemaGenerator } from './features/schema-designer/SchemaDesigner'
export { ERDiagram } from './features/er-diagram/ERDiagram'

interface PageProps {
  title: string
  description: string
}

const PagePlaceholder = ({ title, description }: PageProps) => {
  return (
    <div className="p-6 md:p-10 max-w-4xl">
      <div className="px-4 py-1 text-xs font-semibold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-md inline-block mb-4">
        Placeholder Page
      </div>
      <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-3">
        {title}
      </h1>
      <p className="text-slate-400 text-base leading-relaxed">
        {description}
      </p>
    </div>
  )
}

export { SchemaValidation } from './features/schema-validation/SchemaValidation'

export { DataGeneration } from './features/data-generation/DataGeneration'
export { JobHistory } from './features/job-history/JobHistory'

export { Export } from './features/export/Export'

export const Observability = () => (
  <PagePlaceholder
    title="Observability"
    description="Real-time telemetry, structured application traces, system logs, and generation diagnostics."
  />
)

export const Settings = () => (
  <PagePlaceholder
    title="Settings"
    description="Configure global application properties, API access keys, connection pools, and agent models."
  />
)

export const About = () => {
  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto text-left space-y-8">
      <PageHeader
        title="About & Design System Showcase"
        subtitle="SafeSeed-Ops version 1.0.0-rc1. Reusable primitives and style conventions built with React and Tailwind CSS v4."
      />

      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-200">Button Variants</h2>
        <Stack direction="row" gap="sm">
          <Button variant="primary">Primary Button</Button>
          <Button variant="secondary">Secondary Button</Button>
          <Button variant="outline">Outline Button</Button>
          <Button variant="ghost">Ghost Button</Button>
          <Button variant="danger">Danger Button</Button>
        </Stack>
      </section>

      <Divider label="UI Primitives" />

      <Grid cols={2}>
        <Card hoverable className="space-y-4">
          <h3 className="text-base font-bold text-slate-200">System Badges</h3>
          <Stack direction="row" gap="sm">
            <Badge variant="info">Info</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="error">Error</Badge>
          </Stack>
        </Card>

        <Card hoverable className="flex items-center justify-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <Spinner size="sm" />
            <span className="text-xs text-slate-500">Small</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Spinner size="md" />
            <span className="text-xs text-slate-500">Medium</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Spinner size="lg" />
            <span className="text-xs text-slate-500">Large</span>
          </div>
        </Card>
      </Grid>

      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-200">Alert Messages</h2>
        <Stack gap="sm">
          <Alert variant="info" title="Information Update">
            All system connection endpoints are initialized and running in shell
            configuration mode.
          </Alert>
          <Alert variant="success" title="Quality Gate Verification">
            All backend and frontend package lint, formatting, and unit tests
            completed with zero errors.
          </Alert>
        </Stack>
      </section>
    </div>
  )
}

export const NotFound = () => (
  <PagePlaceholder
    title="404 Not Found"
    description="The page you are looking for does not exist or has been moved."
  />
)
