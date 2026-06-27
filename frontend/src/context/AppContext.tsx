/* eslint-disable react/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react'

export type Theme = 'dark' | 'light'

export interface AppSettings {
  themePreference: Theme | 'system'
  reducedMotion: boolean
}

interface AppContextType {
  version: string
  env: string
  theme: Theme
  setTheme: (theme: Theme) => void
  isSidebarCollapsed: boolean
  setIsSidebarCollapsed: (collapsed: boolean) => void
  isMobileMenuOpen: boolean
  setIsMobileMenuOpen: (open: boolean) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  isGlobalBusy: boolean
  setIsGlobalBusy: (busy: boolean) => void
  currentPageTitle: string
  setCurrentPageTitle: (title: string) => void
  breadcrumbPlaceholder: string
  setBreadcrumbPlaceholder: (text: string) => void
  isModalOpen: boolean
  setIsModalOpen: (open: boolean) => void
  isDialogOpen: boolean
  setIsDialogOpen: (open: boolean) => void
  settings: AppSettings
  updateSettings: (settings: Partial<AppSettings>) => void
}

const AppContext = createContext<AppContextType | undefined>(undefined)

export const AppProvider = ({ children }: { children: React.ReactNode }) => {
  const [settings, setSettings] = useState<AppSettings>(() => {
    const saved = localStorage.getItem('safeseedops_settings')
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch {
        // ignore
      }
    }
    return {
      themePreference: 'system',
      reducedMotion: false,
    }
  })

  const [theme, setThemeState] = useState<Theme>(() => {
    if (settings.themePreference === 'system') {
      const matchDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      return matchDark ? 'dark' : 'light'
    }
    return settings.themePreference
  })

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isGlobalBusy, setIsGlobalBusy] = useState(false)
  const [currentPageTitle, setCurrentPageTitle] = useState('Dashboard')
  const [breadcrumbPlaceholder, setBreadcrumbPlaceholder] =
    useState('Home / Dashboard')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  useEffect(() => {
    const root = window.document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  useEffect(() => {
    if (settings.themePreference !== 'system') return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      setThemeState(e.matches ? 'dark' : 'light')
    }
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [settings.themePreference])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    updateSettings({ themePreference: newTheme })
  }

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings }
      localStorage.setItem('safeseedops_settings', JSON.stringify(updated))
      return updated
    })
  }

  return (
    <AppContext.Provider
      value={{
        version: 'v1.0.0-rc1',
        env: import.meta.env.MODE,
        theme,
        setTheme,
        isSidebarCollapsed,
        setIsSidebarCollapsed,
        isMobileMenuOpen,
        setIsMobileMenuOpen,
        isLoading,
        setIsLoading,
        isGlobalBusy,
        setIsGlobalBusy,
        currentPageTitle,
        setCurrentPageTitle,
        breadcrumbPlaceholder,
        setBreadcrumbPlaceholder,
        isModalOpen,
        setIsModalOpen,
        isDialogOpen,
        setIsDialogOpen,
        settings,
        updateSettings,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useTheme must be used within AppProvider')
  return { theme: context.theme, setTheme: context.setTheme }
}

export const useSidebar = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useSidebar must be used within AppProvider')
  return {
    isSidebarCollapsed: context.isSidebarCollapsed,
    setIsSidebarCollapsed: context.setIsSidebarCollapsed,
    isMobileMenuOpen: context.isMobileMenuOpen,
    setIsMobileMenuOpen: context.setIsMobileMenuOpen,
  }
}

export const useLoading = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useLoading must be used within AppProvider')
  return {
    isLoading: context.isLoading,
    setIsLoading: context.setIsLoading,
    isGlobalBusy: context.isGlobalBusy,
    setIsGlobalBusy: context.setIsGlobalBusy,
  }
}

export const useSettings = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useSettings must be used within AppProvider')
  return { settings: context.settings, updateSettings: context.updateSettings }
}

export const useAppInfo = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useAppInfo must be used within AppProvider')
  return { version: context.version, env: context.env }
}

export const useUIState = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useUIState must be used within AppProvider')
  return {
    currentPageTitle: context.currentPageTitle,
    setCurrentPageTitle: context.setCurrentPageTitle,
    breadcrumbPlaceholder: context.breadcrumbPlaceholder,
    setBreadcrumbPlaceholder: context.setBreadcrumbPlaceholder,
    isModalOpen: context.isModalOpen,
    setIsModalOpen: context.setIsModalOpen,
    isDialogOpen: context.isDialogOpen,
    setIsDialogOpen: context.setIsDialogOpen,
  }
}
