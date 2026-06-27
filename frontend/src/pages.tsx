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

export const Dashboard = () => (
  <PagePlaceholder
    title="Dashboard"
    description="Overview of SafeSeed-Ops system operations, active data generation instances, and agent status metrics."
  />
)

export const Projects = () => (
  <PagePlaceholder
    title="Projects"
    description="Manage your synthetic relational database configuration projects and generation schemas."
  />
)

export const SchemaGenerator = () => (
  <PagePlaceholder
    title="Schema Generator"
    description="Design and configure relational entity schemas, column definitions, and seeding attributes."
  />
)

export const SchemaValidation = () => (
  <PagePlaceholder
    title="Schema Validation"
    description="Trigger multi-agent validation loops to ensure schema integrity and consistency checks."
  />
)

export const DataGeneration = () => (
  <PagePlaceholder
    title="Data Generation"
    description="Configure and execute parallel data generation runs with custom scaling constraints."
  />
)

export const Export = () => (
  <PagePlaceholder
    title="Export"
    description="Export generated datasets to target files including CSV, SQL inserts, or JSON formats."
  />
)

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

export const About = () => (
  <PagePlaceholder
    title="About"
    description="SafeSeed-Ops version 1.0.0. Enterprise-grade synthetic relational database generator using a multi-agent architecture."
  />
)

export const NotFound = () => (
  <PagePlaceholder
    title="404 - Page Not Found"
    description="The requested page could not be located. Please check the sidebar menu or navigation link."
  />
)
