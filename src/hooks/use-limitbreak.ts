import { useState, useEffect, useRef } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import type { LimitBreakData, LimitBreakExecutedData } from '@/types/server'

export type { LimitBreakData }

export function useLimitbreak() {
  const data = useRealtimeStore((s) => s.limitbreak)
  const executedEvent = useRealtimeStore((s) => s.limitbreakExecuted)
  const isConnected = useRealtimeStore((s) => s.isConnected)

  const [hasJustMaxed, setHasJustMaxed] = useState(false)
  const [hasJustExecuted, setHasJustExecuted] = useState(false)
  const [lastExecutionTime, setLastExecutionTime] = useState<string | null>(null)

  const previousIsMaxedRef = useRef<boolean>(false)
  const previousDataRef = useRef<LimitBreakData | null>(null)
  const lastExecutionEventRef = useRef<LimitBreakExecutedData | null>(null)

  // Detect transition to maxed state
  useEffect(() => {
    if (!data) return

    const wasMaxed = previousIsMaxedRef.current
    const isNowMaxed = data.isMaxed

    if (!wasMaxed && isNowMaxed) {
      setHasJustMaxed(true)
    } else {
      setHasJustMaxed(false)
    }

    previousIsMaxedRef.current = isNowMaxed
    previousDataRef.current = data
  }, [data])

  // Detect execution events
  useEffect(() => {
    if (executedEvent && executedEvent !== lastExecutionEventRef.current) {
      lastExecutionEventRef.current = executedEvent

      setHasJustExecuted(true)
      setHasJustMaxed(false)
      setLastExecutionTime(new Date().toISOString())

      setTimeout(() => {
        setHasJustExecuted(false)
      }, 1000)
    }
  }, [executedEvent])

  // Computed values
  const isReady = data?.isMaxed || false
  const progress = {
    bar1: (data?.bar1 || 0) * 100,
    bar2: (data?.bar2 || 0) * 100,
    bar3: (data?.bar3 || 0) * 100,
  }

  const filledBars = {
    bar1: (data?.bar1 || 0) >= 1,
    bar2: (data?.bar2 || 0) >= 1,
    bar3: (data?.bar3 || 0) >= 1,
  }

  const totalBars = [filledBars.bar1, filledBars.bar2, filledBars.bar3].filter(Boolean).length

  return {
    data,
    previousData: previousDataRef.current,
    count: data?.count || 0,
    isReady,
    progress,
    filledBars,
    totalBars,
    hasJustMaxed,
    hasJustExecuted,
    lastExecutionTime,
    lastUpdateTime: null,
    isConnected,
  }
}