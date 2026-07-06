import { useState, useEffect } from 'react'
import {
  Button,
  Card,
  Badge,
  Grid,
  PageHeader,
  EmptyState,
} from '../../components/ui'
import { useProjects } from '../../context/ProjectContext'

export const Projects = () => {
  const { projects, activeProjectId, selectProject, createProject, fetchProjects } = useProjects()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleCreateProject = async () => {
    const name = prompt('Enter Project Name:')
    if (!name) return
    const description =
      prompt('Enter Project Description:') || 'No description provided.'
    await createProject(name, description)
  }

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || p.status === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 text-left">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          title="Project Workspace"
          subtitle="Manage, edit, and orchestrate synthetic schema seeding models."
        />
        <Button
          variant="primary"
          onClick={handleCreateProject}
          className="self-start sm:self-auto flex items-center gap-2"
        >
          <span>➕</span> New Project
        </Button>
      </div>

      {/* Search & Filter Toolbar */}
      <Card className="p-4 flex flex-col md:flex-row gap-4 justify-between items-center bg-slate-900/60 border-slate-800/80">
        <div className="w-full md:w-72 relative">
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
          />
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'all'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('verified')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'verified'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            Verified
          </button>
          <button
            onClick={() => setFilter('pending')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              filter === 'pending'
                ? 'bg-indigo-600/10 text-indigo-300 border-indigo-500/30'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
            }`}
          >
            Pending
          </button>
        </div>
      </Card>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <EmptyState
          title="No Projects Found"
          description="Could not find any projects matching your search. Create a new one to begin designing seeding schemas."
          actionLabel="Create Project"
          onAction={handleCreateProject}
        />
      ) : (
        <Grid cols={3} className="gap-6">
          {filteredProjects.map((p) => (
            <Card
              key={p.id}
              hoverable
              onClick={() => selectProject(p.id)}
              className={`p-6 flex flex-col justify-between h-48 border transition-all cursor-pointer ${
                p.id === activeProjectId
                  ? 'border-indigo-500 bg-indigo-950/20 shadow-lg shadow-indigo-500/10'
                  : 'border-slate-800/80 hover:border-slate-700/60 bg-slate-900/30'
              }`}
            >
              <div className="space-y-2">
                <div className="flex justify-between items-start">
                  <h3 className="font-bold text-slate-200 text-base truncate pr-2">
                    {p.name}
                  </h3>
                  <Badge
                    variant={p.status === 'verified' ? 'success' : 'warning'}
                  >
                    {p.status}
                  </Badge>
                </div>
                <p className="text-slate-400 text-xs line-clamp-3">
                  {p.description}
                </p>
              </div>
              <div className="flex justify-between items-center pt-4 border-t border-slate-800/60 text-[10px] text-slate-500">
                <span>📊 {p.tables} tables</span>
                <span>Last updated: {p.updated_at ? p.updated_at.split('T')[0] : 'N/A'}</span>
              </div>
            </Card>
          ))}
        </Grid>
      )}
    </div>
  )
}
