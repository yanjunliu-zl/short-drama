import { useCallback, useRef } from 'react'
import { useSelector } from 'react-redux'
import type { RootState } from '@/store'
import { pipelineService, type PipelineState } from '@/services/pipelineService'

type SliceKey = 'script' | 'scenes' | 'characters' | 'props' | 'storyboard' | 'videoResults' | 'finalCut'

const SLICE_KEYS: SliceKey[] = ['script', 'scenes', 'characters', 'props', 'storyboard', 'videoResults', 'finalCut']

/** Build user-namespaced localStorage key */
export function storageKey(userId: string, baseKey: string): string {
  return `pipeline_${userId}_${baseKey}`
}

export function usePipelinePersistence() {
  const user = useSelector((state: RootState) => state.auth.user)
  const userId = (user as any)?.id || 'anonymous'
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  /**
   * Save a slice of pipeline state to localStorage (user-namespaced) and
   * debounce-save to backend when a workId is known.
   */
  const saveState = useCallback(
    (key: SliceKey, value: any, workId?: string) => {
      // Always save to localStorage with user namespace
      try {
        localStorage.setItem(storageKey(userId, key), JSON.stringify(value))
      } catch { /* quota exceeded, ignore */ }

      // Debounce backend save
      if (workId) {
        const timerKey = `save_${workId}`
        if (debounceTimers.current[timerKey]) {
          clearTimeout(debounceTimers.current[timerKey])
        }
        debounceTimers.current[timerKey] = setTimeout(async () => {
          try {
            // 串行化：同一 workId 的多次保存排队执行，避免竞态覆盖
            const saveKey = `_save_lock_${workId}`
            const prev = (window as any)[saveKey] || Promise.resolve()
            const next = prev.then(async () => {
              let existing: any = {}
              try {
                const resp = await pipelineService.getPipelineState(workId)
                existing = resp.data || {}
              } catch {}
              existing[key] = value
              existing.updatedAt = new Date().toISOString()
              await pipelineService.savePipelineState(workId, existing)
            }).catch((err: any) => {
              console.error('Auto-save pipeline state failed:', err)
            })
            ;(window as any)[saveKey] = next
            await next
          } catch (err) {
            console.error('Auto-save pipeline state failed:', err)
          }
        }, 2000)
      }
    },
    [userId],
  )

  /**
   * Load a slice of pipeline state from localStorage.
   */
  const loadState = useCallback(
    (key: SliceKey): any | null => {
      try {
        const saved = localStorage.getItem(storageKey(userId, key))
        if (saved) return JSON.parse(saved)
      } catch { /* corrupt data */ }
      return null
    },
    [userId],
  )

  /**
   * Load ALL pipeline state from backend for a given workId and restore to localStorage.
   */
  const restoreFromBackend = useCallback(
    async (workId: string): Promise<boolean> => {
      try {
        const response = await pipelineService.getPipelineState(workId)
        if (response.data) {
          // Only clear after successful fetch, not before
          clearPipelineStorage(userId)
          for (const key of SLICE_KEYS) {
            const value = (response.data as any)[key]
            if (value) {
              localStorage.setItem(storageKey(userId, key), JSON.stringify(value))
            }
          }
          localStorage.setItem(storageKey(userId, 'workId'), workId)
          return true
        }
        // Even without data, remember workId
        localStorage.setItem(storageKey(userId, 'workId'), workId)
        return false
      } catch (err) {
        console.error('Restore pipeline state from backend failed:', err)
        return false
      }
    },
    [userId],
  )

  /** Get the current active workId from localStorage */
  const getWorkId = useCallback((): string | null => {
    return localStorage.getItem(storageKey(userId, 'workId'))
  }, [userId])

  /** Set the current active workId */
  const setWorkId = useCallback(
    (workId: string) => {
      localStorage.setItem(storageKey(userId, 'workId'), workId)
    },
    [userId],
  )

  /**
   * 一次性保存所有 key 到后端（原子操作，防止分 key 保存的竞态覆盖）
   */
  const saveAllToBackend = useCallback(
    async (workId: string, updates?: Record<string, any>) => {
      const fullState = buildFullState(userId)
      if (updates) {
        for (const [k, v] of Object.entries(updates)) {
          fullState[k as keyof PipelineState] = v
          // 同步写 localStorage
          try { localStorage.setItem(storageKey(userId, k), JSON.stringify(v)) } catch {}
        }
      }
      fullState.updatedAt = new Date().toISOString()
      // 串行化：同一 workId 的多次保存排队执行
      const saveKey = `_save_lock_${workId}`
      const prev = (window as any)[saveKey] || Promise.resolve()
      const next = prev.then(async () => {
        await pipelineService.savePipelineState(workId, fullState)
      }).catch((err: any) => {
        console.error('saveAllToBackend failed:', err)
      })
      ;(window as any)[saveKey] = next
      return next
    },
    [userId],
  )

  return { saveState, loadState, loadPersisted: loadState, restoreFromBackend, getWorkId, setWorkId, userId, saveAllToBackend }
}

/** Build full PipelineState from all localStorage keys for a user */
function buildFullState(userId: string): PipelineState {
  const state: any = {}
  for (const key of SLICE_KEYS) {
    try {
      const raw = localStorage.getItem(`pipeline_${userId}_${key}`)
      if (raw) state[key] = JSON.parse(raw)
    } catch { /* skip corrupt key */ }
  }
  return state
}

/** Clear all pipeline-related localStorage keys for a user (call on logout) */
export function clearPipelineStorage(userId: string) {
  const allKeys = [...SLICE_KEYS, 'workId']
  for (const key of allKeys) {
    try {
      localStorage.removeItem(storageKey(userId, key))
    } catch { /* ignore */ }
  }
}
