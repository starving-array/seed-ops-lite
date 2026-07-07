export const API_CONFIG = {
  baseUrl:
    (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000',
  timeout: parseInt(
    (import.meta.env.VITE_API_TIMEOUT as string) || '120000',
    10
  ),
  defaultHeaders: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
}
