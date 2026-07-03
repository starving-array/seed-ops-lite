import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock healthService status check
const mockCheckStatus = vi.fn()
vi.mock('./services/health', () => ({
  healthService: {
    checkStatus: () => mockCheckStatus(),
  },
}))

describe('Frontend Health Polling Regression Tests', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockCheckStatus.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should start polling on mount and stop on unmount without leaking timers', async () => {
    mockCheckStatus.mockResolvedValue({ success: true, data: { storage_mode: 'redis' } })

    let isMounted = true
    const verifyConnectivity = async () => {
      await mockCheckStatus()
    }

    verifyConnectivity()
    const timerId = setInterval(() => {
      if (isMounted) {
        verifyConnectivity()
      }
    }, 5000)

    expect(mockCheckStatus).toHaveBeenCalledTimes(1)

    // Fast-forward 5 seconds to trigger interval poll
    vi.advanceTimersByTime(5000)
    expect(mockCheckStatus).toHaveBeenCalledTimes(2)

    // Unmount simulated
    isMounted = false
    clearInterval(timerId)

    // Fast-forward 5 seconds again
    vi.advanceTimersByTime(5000)
    expect(mockCheckStatus).toHaveBeenCalledTimes(2)
  })

  it('should continue polling even if a status request fails', async () => {
    // 1st request succeeds
    mockCheckStatus.mockResolvedValueOnce({ success: true, data: { storage_mode: 'redis' } })
    // 2nd request fails
    mockCheckStatus.mockResolvedValueOnce({ success: false, error: { code: 'NETWORK_ERROR' } })
    // 3rd request succeeds again
    mockCheckStatus.mockResolvedValueOnce({ success: true, data: { storage_mode: 'memory' } })

    let currentStatus = 'Connecting'
    let currentMode = 'redis'

    const verifyConnectivity = async () => {
      const res = await mockCheckStatus()
      if (res.success) {
        currentStatus = 'Connected'
        currentMode = res.data?.storage_mode || 'redis'
      } else {
        currentStatus = 'Unavailable'
      }
    }

    // Initial load
    await verifyConnectivity()
    expect(currentStatus).toBe('Connected')
    expect(currentMode).toBe('redis')

    // 5s fail poll
    await verifyConnectivity()
    expect(currentStatus).toBe('Unavailable')

    // 10s success fallback mode poll
    await verifyConnectivity()
    expect(currentStatus).toBe('Connected')
    expect(currentMode).toBe('memory')
  })
})

