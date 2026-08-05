import { useState, useEffect, useRef, useCallback } from 'react'
import { usePipelinePersistence } from './usePipelinePersistence'

interface PresenceInfo {
  userId: string
  timestamp: number
}

/**
 * 多用户协作 Hook — WebSocket 实时同步
 *
 * 按需连接：仅当 enabled=true 时建立 WebSocket。
 * 对标 LibTV：WebSocket 连接 + Redis pub/sub 跨实例广播
 */
export function useCollaboration(workId: string | null, page: string, enabled = false) {
  const { userId, restoreFromBackend } = usePipelinePersistence()
  const [remoteUsers, setRemoteUsers] = useState<PresenceInfo[]>([])
  const [hasRemoteChanges, setHasRemoteChanges] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (!workId || !userId || !enabled) return
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/collaboration?workId=${workId}&userId=${userId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      // 发送心跳
      const ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' })) }, 25000)
      ws.addEventListener('close', () => clearInterval(ping))
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'presence_join':
            setRemoteUsers(prev => {
              const filtered = prev.filter(u => u.userId !== msg.userId)
              return [...filtered, { userId: msg.userId, timestamp: msg.timestamp }]
            })
            break
          case 'presence_leave':
            setRemoteUsers(prev => prev.filter(u => u.userId !== msg.userId))
            break
          case 'pipeline_update':
            if (msg.userId !== userId) setHasRemoteChanges(true)
            break
          case 'pong':
            break
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      setWsConnected(false)
      setRemoteUsers([])
      reconnectRef.current = setTimeout(connect, 5000)
    }

    ws.onerror = () => { ws.close() }
  }, [workId, userId, enabled])

  useEffect(() => {
    if (enabled) connect()
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      if (wsRef.current) { wsRef.current.close(); setWsConnected(false); setRemoteUsers([]); }
    }
  }, [connect, enabled])

  /** 保存 pipeline 后通知其他用户 */
  const notifyPipelineSave = useCallback((updatedAt: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'pipeline_save', userId, updatedAt }))
    }
  }, [userId])

  /** 同步远程变更到本地 */
  const syncFromRemote = useCallback(async () => {
    if (!workId) return
    await restoreFromBackend(workId)
    setHasRemoteChanges(false)
    window.location.reload()
  }, [workId, restoreFromBackend])

  return { remoteUsers, hasRemoteChanges, syncFromRemote, wsConnected, notifyPipelineSave }
}
