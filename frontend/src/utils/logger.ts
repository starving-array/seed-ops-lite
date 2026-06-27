const IS_DEV = import.meta.env.DEV

export const logger = {
  debug: (message: string, ...args: any[]) => {
    if (IS_DEV) {
      console.debug(`[DEBUG] ${message}`, ...args)
    }
  },
  info: (message: string, ...args: any[]) => {
    if (IS_DEV) {
      console.info(`[INFO] ${message}`, ...args)
    }
  },
  warn: (message: string, ...args: any[]) => {
    if (IS_DEV) {
      console.warn(`[WARN] ${message}`, ...args)
    }
  },
  error: (message: string, error?: Error | unknown, ...args: any[]) => {
    if (IS_DEV) {
      console.error(`[ERROR] ${message}`, error, ...args)
    }
  },
}
