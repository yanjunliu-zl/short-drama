import { useState, useEffect, useCallback } from 'react'

/** 用户信用额度 Hook */
export function useCredits(userId: string | undefined) {
  const [balance, setBalance] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchBalance = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/credits/balance?userId=${userId}`)
      if (resp.ok) {
        const data = await resp.json()
        setBalance(data.balanceYuan ?? data.balance / 100)
      }
    } catch { /* ignore */ }
    setLoading(false)
  }, [userId])

  useEffect(() => { fetchBalance() }, [fetchBalance])

  /** 扣减后刷新余额 */
  const refreshAfterDeduct = useCallback(async () => {
    await fetchBalance()
  }, [fetchBalance])

  return { balance, loading, refreshAfterDeduct }
}
