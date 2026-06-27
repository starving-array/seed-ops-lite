import { useState } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
  Navigate,
} from 'react-router-dom'
import {
  Dashboard,
  Projects,
  SchemaGenerator,
  SchemaValidation,
  DataGeneration,
  Export,
  Observability,
  Settings,
  About,
  NotFound,
} from './pages'

function App() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/projects', label: 'Projects', icon: '📁' },
    { path: '/schema-generator', label: 'Schema Generator', icon: '🛠️' },
    { path: '/schema-validation', label: 'Schema Validation', icon: '🛡️' },
    { path: '/data-generation', label: 'Data Generation', icon: '⚙️' },
    { path: '/export', label: 'Export', icon: '📥' },
    { path: '/observability', label: 'Observability', icon: '📈' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
    { path: '/about', label: 'About', icon: 'ℹ️' },
  ]

  return (
    <Router>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
        {/* Main Application Container */}
        <div className="flex flex-1 relative overflow-hidden">
          {/* 1. SIDEBAR (Aside landmark) */}
          <aside
            aria-label="Primary Navigation"
            className={`
              fixed lg:static top-0 bottom-0 left-0 z-40
              bg-slate-900 border-r border-slate-800/80
              flex flex-col transition-all duration-300 ease-in-out
              ${isSidebarCollapsed ? 'lg:w-20' : 'lg:w-64'}
              ${isMobileMenuOpen ? 'translate-x-0 w-64' : '-translate-x-full lg:translate-x-0'}
            `}
          >
            {/* Logo Area */}
            <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800/80">
              <div className="flex items-center gap-3 overflow-hidden">
                <span className="text-2xl" role="img" aria-label="Seed Logo">
                  🌱
                </span>
                {!isSidebarCollapsed && (
                  <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white to-indigo-300 bg-clip-text text-transparent">
                    SafeSeed-Ops
                  </span>
                )}
              </div>
              {/* Mobile Close Button */}
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                className="lg:hidden text-slate-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-md p-1"
                aria-label="Close sidebar"
              >
                ✕
              </button>
            </div>

            {/* Navigation Links */}
            <nav className="flex-1 py-4 overflow-y-auto px-3 space-y-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={({ isActive }) => `
                    flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-200 group
                    focus:outline-none focus:ring-2 focus:ring-indigo-500
                    ${
                      isActive
                        ? 'bg-indigo-600/15 text-indigo-300 border-l-4 border-indigo-500 font-semibold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border-l-4 border-transparent'
                    }
                  `}
                >
                  <span className="text-xl shrink-0" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span
                    className={`
                    transition-opacity duration-300 truncate
                    ${isSidebarCollapsed ? 'lg:opacity-0 lg:w-0' : 'opacity-100'}
                  `}
                  >
                    {item.label}
                  </span>
                </NavLink>
              ))}
            </nav>

            {/* Collapse Toggle Button (Desktop only) */}
            <div className="hidden lg:block p-4 border-t border-slate-800/80">
              <button
                onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                className="w-full flex items-center justify-center py-2 px-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 hover:text-white border border-slate-700/50 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
                aria-label={
                  isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'
                }
              >
                {isSidebarCollapsed ? '➡️' : '⬅️'}
              </button>
            </div>
          </aside>

          {/* Mobile Overlay Background (drawer backdrop) */}
          {isMobileMenuOpen && (
            <div
              onClick={() => setIsMobileMenuOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
              aria-hidden="true"
            />
          )}

          {/* Right Work Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
            {/* 2. HEADER (Header landmark) */}
            <header className="h-16 bg-slate-900/50 border-b border-slate-800/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-20">
              {/* Left Side: Mobile Menu Button + Title */}
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsMobileMenuOpen(true)}
                  className="lg:hidden text-slate-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-md p-1"
                  aria-label="Open navigation menu"
                >
                  <span className="text-2xl">☰</span>
                </button>
                <div className="font-semibold text-slate-200 text-lg">
                  Shell Workspace
                </div>
              </div>

              {/* Right Side: Placeholders for theme/settings */}
              <div className="flex items-center gap-3">
                {/* Theme Toggle Placeholder */}
                <button
                  type="button"
                  className="p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-amber-400 border border-slate-700/40 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-not-allowed"
                  aria-label="Toggle theme (Placeholder)"
                  disabled
                >
                  ☀️
                </button>

                {/* Settings Toggle Placeholder */}
                <button
                  type="button"
                  className="p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-indigo-400 border border-slate-700/40 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-not-allowed"
                  aria-label="Configure shell settings (Placeholder)"
                  disabled
                >
                  ⚙️
                </button>
              </div>
            </header>

            {/* 3. MAIN CONTENT (Main landmark) */}
            <main
              id="main-content"
              className="flex-1 focus:outline-none"
              tabIndex={-1}
            >
              <Routes>
                <Route
                  path="/"
                  element={<Navigate to="/dashboard" replace />}
                />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/projects" element={<Projects />} />
                <Route path="/schema-generator" element={<SchemaGenerator />} />
                <Route
                  path="/schema-validation"
                  element={<SchemaValidation />}
                />
                <Route path="/data-generation" element={<DataGeneration />} />
                <Route path="/export" element={<Export />} />
                <Route path="/observability" element={<Observability />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/about" element={<About />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </main>

            {/* 4. FOOTER (Footer landmark) */}
            <footer className="py-6 px-6 bg-slate-900 border-t border-slate-800/80 text-center md:flex md:items-center md:justify-between text-xs text-slate-500">
              <div>
                Version Placeholder:{' '}
                <span className="font-semibold text-slate-400">v1.0.0-rc1</span>
              </div>
              <div className="mt-2 md:mt-0">
                SafeSeed-Ops &copy; 2026. Licensed under{' '}
                <a
                  href="/LICENSE"
                  className="text-indigo-400 hover:text-indigo-300 font-semibold focus:outline-none focus:underline"
                >
                  Apache-2.0
                </a>
                .
              </div>
            </footer>
          </div>
        </div>
      </div>
    </Router>
  )
}

export default App
