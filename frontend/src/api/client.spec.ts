import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiClient } from './client'

describe('ApiClient Request Cancellation & Lifecycle Tests', () => {
  let client: ApiClient
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    client = new ApiClient()
    originalFetch = global.fetch
    vi.useFakeTimers()
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('should clean up the timeout timer on successful request resolution', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true }),
    }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    const clearSpy = vi.spyOn(global, 'clearTimeout')

    await client.request('/health')

    expect(clearSpy).toHaveBeenCalled()
  })

  it('should clean up the timeout timer on request rejection', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network Error'))

    const clearSpy = vi.spyOn(global, 'clearTimeout')

    await client.request('/health')

    expect(clearSpy).toHaveBeenCalled()
  })

  it('should remove abort event listener from signal upon request resolution', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true }),
    }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    const controller = new AbortController()
    const signal = controller.signal

    const removeSpy = vi.spyOn(signal, 'removeEventListener')

    await client.request('/health', { signal })

    expect(removeSpy).toHaveBeenCalledWith('abort', expect.any(Function))
  })

  it('should isolate cancellation and not affect concurrent or future requests', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true }),
    }

    global.fetch = vi.fn().mockImplementation((_url, init) => {
      return new Promise((resolve, reject) => {
        if (init?.signal?.aborted) {
          const err = new Error('The user aborted a request.')
          err.name = 'AbortError'
          return reject(err)
        }
        if (init?.signal) {
          init.signal.addEventListener('abort', () => {
            const err = new Error('The user aborted a request.')
            err.name = 'AbortError'
            reject(err)
          })
        }
        // If it's the schema request, resolve it, else wait/simulate abort
        if (_url.includes('/schema')) {
          resolve(mockResponse)
        }
      })
    })

    const controller1 = new AbortController()
    const req1 = client.request('/health', { signal: controller1.signal })

    const controller2 = new AbortController()
    const req2 = client.request('/schema', { signal: controller2.signal })

    // Cancel req1 only
    controller1.abort()
    const res1 = await req1
    expect(res1.success).toBe(false)
    expect(res1.error?.code).toBe('TIMEOUT') // normalized code for AbortError

    const res2 = await req2
    expect(res2.success).toBe(true)
  })
})
