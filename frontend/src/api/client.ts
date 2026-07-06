import { API_CONFIG } from './config'
import type { ApiResponse, ApiError } from '../types/api'
import { logger } from '../utils/logger'

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: any
  timeout?: number
  retries?: number
  retryDelay?: number
}

export class ApiClient {
  private baseUrl: string
  private defaultHeaders: Record<string, string>
  private timeout: number

  constructor() {
    this.baseUrl = API_CONFIG.baseUrl
    this.defaultHeaders = API_CONFIG.defaultHeaders
    this.timeout = API_CONFIG.timeout
  }

  private normalizeError(error: any): ApiError {
    if (error.name === 'AbortError') {
      return {
        code: 'TIMEOUT',
        message:
          'The request timed out. Please check your connection speed and retry.',
      }
    }
    if (
      error instanceof TypeError &&
      error.message.includes('Failed to fetch')
    ) {
      return {
        code: 'NETWORK_ERROR',
        message:
          'Network unavailable. Please verify you are online and that the backend service is running.',
      }
    }
    return {
      code: 'UNEXPECTED_ERROR',
      message: error.message || 'An unexpected error occurred.',
    }
  }

  async request<T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      method = 'GET',
      headers = {},
      body,
      timeout = this.timeout,
      retries = 0,
      retryDelay = 1000,
      signal,
      ...customInit
    } = options

    const url = `${this.baseUrl}${path.startsWith('/') ? path : '/' + path}`
    const activeProject =
      (typeof localStorage !== 'undefined'
        ? localStorage.getItem('active_project_id')
        : null) || 'default'
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
    const mergedHeaders: Record<string, string> = {
      ...this.defaultHeaders,
      'X-Project-Id': activeProject,
      ...(headers as Record<string, string>),
    }
    if (isFormData) {
      delete mergedHeaders['Content-Type']
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    let abortHandler: (() => void) | null = null

    if (signal) {
      abortHandler = () => {
        controller.abort()
        clearTimeout(timeoutId)
      }
      signal.addEventListener('abort', abortHandler)
    }

    const init: RequestInit = {
      method,
      headers: mergedHeaders,
      signal: controller.signal,
      ...customInit,
    }

    if (body) {
      init.body = isFormData ? body : (typeof body === 'object' ? JSON.stringify(body) : body)
    }

    logger.debug(`API Request: [${method}] -> ${url}`, {
      body,
      headers: mergedHeaders,
    })

    try {
      const response = await fetch(url, init)

      const responseText = await response.text()
      let responseData: any = null
      if (responseText) {
        try {
          responseData = JSON.parse(responseText)
        } catch {
          responseData = responseText
        }
      }

      logger.debug(
        `API Response: [${method}] <- ${url} [Status: ${response.status}]`,
        responseData
      )

      if (response.ok) {
        return {
          success: true,
          data: responseData as T,
        }
      }

      let apiError: ApiError
      if (response.status === 422) {
        apiError = {
          code: 'VALIDATION_ERROR',
          message: 'The submitted fields did not pass validation.',
          details: responseData?.detail || responseData,
        }
      } else if (response.status >= 500) {
        apiError = {
          code: 'SERVER_ERROR',
          message:
            'Backend server encountered an error. Please try again later.',
          details: responseData,
        }
      } else {
        apiError = {
          code: responseData?.code || 'API_ERROR',
          message:
            responseData?.message ||
            `API request failed with status code ${response.status}`,
          details: responseData?.details || responseData,
        }
      }

      return {
        success: false,
        error: apiError,
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        logger.error(`API Request Failed: [${method}] -> ${url}`, err)
      } else {
        logger.debug(`API Request Cancelled: [${method}] -> ${url}`)
      }

      if (retries > 0 && err.name !== 'AbortError') {
        logger.warn(
          `Retrying request [${method}] -> ${url}. Retries remaining: ${retries}`
        )
        await new Promise((resolve) => setTimeout(resolve, retryDelay))
        return this.request<T>(path, { ...options, retries: retries - 1 })
      }

      return {
        success: false,
        error: this.normalizeError(err),
      }
    } finally {
      clearTimeout(timeoutId)
      if (signal && abortHandler) {
        signal.removeEventListener('abort', abortHandler)
      }
    }
  }

  async get<T>(
    path: string,
    options?: Omit<RequestOptions, 'method' | 'body'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, { ...options, method: 'GET' })
  }

  async post<T>(
    path: string,
    body?: any,
    options?: Omit<RequestOptions, 'method' | 'body'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, { ...options, method: 'POST', body })
  }

  async put<T>(
    path: string,
    body?: any,
    options?: Omit<RequestOptions, 'method' | 'body'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, { ...options, method: 'PUT', body })
  }

  async patch<T>(
    path: string,
    body?: any,
    options?: Omit<RequestOptions, 'method' | 'body'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, { ...options, method: 'PATCH', body })
  }

  async delete<T>(
    path: string,
    options?: Omit<RequestOptions, 'method' | 'body'>
  ): Promise<ApiResponse<T>> {
    return this.request<T>(path, { ...options, method: 'DELETE' })
  }
}

export const apiClient = new ApiClient()
