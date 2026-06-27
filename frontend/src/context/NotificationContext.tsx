/* eslint-disable react/only-export-components */
import { createContext, useContext, useState, useCallback } from 'react'
import { Alert } from '../components/ui'

export type NotificationType = 'success' | 'info' | 'warning' | 'error'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  message?: string
  duration?: number
}

interface NotificationContextType {
  notifications: Notification[]
  addNotification: (notification: Omit<Notification, 'id'>) => string
  removeNotification: (id: string) => void
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
)

export const NotificationProvider = ({
  children,
}: {
  children: React.ReactNode
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  const addNotification = useCallback(
    ({ type, title, message, duration = 5000 }: Omit<Notification, 'id'>) => {
      const id = Math.random().toString(36).substring(2, 9)
      const newNotification: Notification = {
        id,
        type,
        title,
        message,
        duration,
      }

      setNotifications((prev) => [...prev, newNotification])

      if (duration > 0) {
        setTimeout(() => {
          removeNotification(id)
        }, duration)
      }

      return id
    },
    [removeNotification]
  )

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        addNotification,
        removeNotification,
      }}
    >
      {children}
      {/* Toast Overlay Container */}
      <div
        className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none"
        aria-live="assertive"
      >
        {notifications.map((n) => (
          <div key={n.id} className="pointer-events-auto shadow-2xl">
            <Alert
              variant={n.type}
              title={n.title}
              onClose={() => removeNotification(n.id)}
            >
              {n.message}
            </Alert>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  )
}

export const useNotifications = () => {
  const context = useContext(NotificationContext)
  if (!context)
    throw new Error(
      'useNotifications must be used within NotificationProvider'
    )
  return {
    notifications: context.notifications,
    addNotification: context.addNotification,
    removeNotification: context.removeNotification,
  }
}
