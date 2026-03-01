import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useServer } from './use-server'
import type { LimitBreakData, LimitBreakExecutedData } from '@/types/server'

export type { LimitBreakData }

export interface LimitBreakState {
  data: LimitBreakData | null
  previousData: LimitBreakData | null
  hasJustMaxed: boolean
  hasJustExecuted: boolean
  lastExecutionTime: string | null
  lastUpdateTime: string | null
}

export function useLimitbreak() {
  const [limitBreakState, setLimitBreakState] = useState<LimitBreakState>({
    data: null,
    previousData: null,
    hasJustMaxed: false,
    hasJustExecuted: false,
    lastExecutionTime: null,
    lastUpdateTime: null,
  })
  
  // Track for edge detection
  const previousIsMaxedRef = useRef<boolean>(false)
  const lastExecutionEventRef = useRef<LimitBreakExecutedData | null>(null)
  
  // Memoize the message types array to prevent infinite loops
  const messageTypes = useMemo(() => ['limitbreak:sync', 'limitbreak:update', 'limitbreak:executed'] as const, [])
  const { data, isConnected } = useServer(messageTypes)

  const updateLimitBreakState = useCallback((newData: LimitBreakData, _isSync: boolean = false) => {
    setLimitBreakState(prev => {
      const wasMaxed = prev.data?.isMaxed || false
      const isNowMaxed = newData.isMaxed
      
      // Detect transition to maxed state
      const justMaxed = !wasMaxed && isNowMaxed
      
      return {
        data: newData,
        previousData: prev.data,
        hasJustMaxed: justMaxed,
        hasJustExecuted: false, // Reset on regular updates
        lastExecutionTime: prev.lastExecutionTime,
        lastUpdateTime: new Date().toISOString(),
      }
    })
    
    // Update ref for next comparison
    previousIsMaxedRef.current = newData.isMaxed
  }, [])

  // Handle sync events
  useEffect(() => {
    if (data['limitbreak:sync']) {
      updateLimitBreakState(data['limitbreak:sync'], true)
    }
  }, [data['limitbreak:sync'], updateLimitBreakState])

  // Handle update events
  useEffect(() => {
    if (data['limitbreak:update']) {
      updateLimitBreakState(data['limitbreak:update'], false)
    }
  }, [data['limitbreak:update'], updateLimitBreakState])

  // Handle execution events
  useEffect(() => {
    const executedEvent = data['limitbreak:executed']
    
    if (executedEvent && executedEvent !== lastExecutionEventRef.current) {
      lastExecutionEventRef.current = executedEvent
      
      setLimitBreakState(prev => ({
        ...prev,
        hasJustExecuted: true,
        hasJustMaxed: false, // Clear maxed flag on execution
        lastExecutionTime: new Date().toISOString(),
      }))
      
      // Clear the execution flag after a short delay
      setTimeout(() => {
        setLimitBreakState(prev => ({
          ...prev,
          hasJustExecuted: false,
        }))
      }, 1000)
    }
  }, [data['limitbreak:executed']])

  // Computed values
  const isReady = limitBreakState.data?.isMaxed || false
  const progress = {
    bar1: (limitBreakState.data?.bar1 || 0) * 100,
    bar2: (limitBreakState.data?.bar2 || 0) * 100,
    bar3: (limitBreakState.data?.bar3 || 0) * 100,
  }
  
  const filledBars = {
    bar1: (limitBreakState.data?.bar1 || 0) >= 1,
    bar2: (limitBreakState.data?.bar2 || 0) >= 1,
    bar3: (limitBreakState.data?.bar3 || 0) >= 1,
  }
  
  const totalBars = [filledBars.bar1, filledBars.bar2, filledBars.bar3].filter(Boolean).length

  return {
    data: limitBreakState.data,
    previousData: limitBreakState.previousData,
    count: limitBreakState.data?.count || 0,
    isReady,
    progress,
    filledBars,
    totalBars,
    hasJustMaxed: limitBreakState.hasJustMaxed,
    hasJustExecuted: limitBreakState.hasJustExecuted,
    lastExecutionTime: limitBreakState.lastExecutionTime,
    lastUpdateTime: limitBreakState.lastUpdateTime,
    isConnected,
  }
}