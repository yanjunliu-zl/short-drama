import { useCallback, useRef } from 'react'
import { useSelector } from 'react-redux'
import type { RootState } from '@/store'
import { pipelineService, type PipelineStep, type PipelineState, VALID_STEPS } from '@/services/pipelineService'

/** Build user+work-namespaced localStorage key to prevent cross-work data pollution */
function cacheKey(userId: string, step: PipelineStep | 'workId', workId?: string | null): string {
  // workId key is always global (not per-work) — chicken-and-egg problem otherwise
  if (step === 'workId') return `pipeline_cache_${userId}_workId`
  const wid = workId || _readWorkId(userId)
  if (wid) {
    return `pipeline_cache_${userId}_${wid}_${step}`
  }
  return `pipeline_cache_${userId}__noid_${step}`
}

function _readWorkId(userId: string): string | null {
  try {
    return localStorage.getItem(`pipeline_cache_${userId}_workId`)
  } catch { return null }
}

/**
 * usePipelinePersistence — backend-first pipeline state management.
 *
 * Architecture:
 *   Backend (Redis hash) = source of truth
 *   localStorage = read-through cache ONLY (fast first render, then backend overrides)
 *
 * Key design: pipeline:{workId} HSET step value
 *   - PUT  /api/v1/works/:id/pipeline/:step  → atomic single-field write, no read-before-write
 *   - GET  /api/v1/works/:id/pipeline/:step  → Redis HGET with MySQL fallback on miss
 */
export function usePipelinePersistence() {
  const user = useSelector((state: RootState) => state.auth.user)
  const userId = (user as any)?.id || 'anonymous'
  // Track in-flight requests to avoid duplicate fetches
  const pendingFetches = useRef<Record<string, Promise<any>>>({})

  /**
   * Save one step to backend (source of truth), then sync localStorage cache.
   * Uses per-step endpoint — atomic, no read-before-write, no cross-step race.
   */
  const saveState = useCallback(
    async (key: PipelineStep, value: any, workId?: string): Promise<void> => {
      // Always sync localStorage cache
      try {
        localStorage.setItem(cacheKey(userId, key, workId), JSON.stringify(value))
      } catch { /* quota exceeded, ignore */ }

      // Write to backend (source of truth)
      if (workId && workId.startsWith('wk_')) {
        try {
          await pipelineService.savePipelineStep(workId, key, value)
        } catch (err) {
          console.error(`[pipeline] saveState "${key}" failed:`, err)
        }
      }
    },
    [userId],
  )

  /**
   * Load one step from backend (source of truth). Falls back to localStorage cache
   * for instant first render, but always returns backend data as final result.
   */
  const loadState = useCallback(
    async (key: PipelineStep, workId?: string): Promise<any | null> => {
      // 1. Read cache for instant first render (caller should use this, then replace with backend)
      let cached: any = null
      try {
        const raw = localStorage.getItem(cacheKey(userId, key, workId))
        if (raw) cached = JSON.parse(raw)
      } catch { /* corrupt, ignore */ }

      // 2. Fetch from backend (source of truth)
      if (workId && workId.startsWith('wk_')) {
        const fetchKey = `${workId}_${key}`
        // Deduplicate in-flight requests
        if (!pendingFetches.current[fetchKey]) {
          pendingFetches.current[fetchKey] = pipelineService
            .getPipelineStep(workId, key)
            .then(resp => {
              delete pendingFetches.current[fetchKey]
              if (resp.data) {
                // Sync cache with backend truth
                try {
                  localStorage.setItem(cacheKey(userId, key, workId), JSON.stringify(resp.data))
                } catch {}
              }
              return resp.data ?? null
            })
            .catch(err => {
              delete pendingFetches.current[fetchKey]
              console.error(`[pipeline] loadState "${key}" failed:`, err)
              return cached // fallback to cache on error
            })
        }
        return pendingFetches.current[fetchKey]
      }

      // No workId — return cache only
      return cached
    },
    [userId],
  )

  /**
   * Synchronous cache read — for initial UI render before backend responds.
   * Call loadState() in useEffect to get the authoritative value.
   */
  const loadCached = useCallback(
    (key: PipelineStep, workId?: string): any | null => {
      try {
        const raw = localStorage.getItem(cacheKey(userId, key, workId))
        if (raw) return JSON.parse(raw)
      } catch {}
      return null
    },
    [userId],
  )

  /**
   * Load ALL steps from backend and sync cache.
   * Use on first visit to a work (e.g. from URL deep-link).
   */
  const restoreFromBackend = useCallback(
    async (workId: string): Promise<boolean> => {
      if (!workId || !workId.startsWith('wk_')) return false
      try {
        const response = await pipelineService.getPipelineState(workId)
        if (response.data) {
          for (const key of VALID_STEPS) {
            const value = (response.data as any)[key]
            if (value && !(Array.isArray(value) && value.length === 0)) {
              try {
                localStorage.setItem(cacheKey(userId, key, workId), JSON.stringify(value))
              } catch {}
            }
          }
          localStorage.setItem(cacheKey(userId, 'workId'), workId)
          return true
        }
        localStorage.setItem(cacheKey(userId, 'workId'), workId)
        return false
      } catch (err) {
        console.error('[pipeline] restoreFromBackend failed:', err)
        return false
      }
    },
    [userId],
  )

  const getWorkId = useCallback((): string | null => {
    const id = localStorage.getItem(cacheKey(userId, 'workId'))
    if (id && !id.startsWith('wk_')) {
      localStorage.removeItem(cacheKey(userId, 'workId'))
      return null
    }
    return id || null
  }, [userId])

  const setWorkId = useCallback(
    (workId: string) => {
      if (workId && workId !== 'default') {
        localStorage.setItem(cacheKey(userId, 'workId'), workId)
      }
    },
    [userId],
  )

  return {
    saveState,
    loadState,
    loadCached,
    restoreFromBackend,
    getWorkId,
    setWorkId,
    userId,
  }
}

/** Clear all pipeline cache for a user (call on logout) */
export function clearPipelineStorage(userId: string) {
  const allSteps = [...VALID_STEPS, 'workId'] as const
  for (const step of allSteps) {
    try {
      localStorage.removeItem(cacheKey(userId, step))
    } catch {}
  }
}
