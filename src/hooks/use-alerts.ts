import { useState, useMemo, useCallback, useEffect, useRef } from 'react'

import { useRealtimeStore } from '@/store/realtime'
import type { AlertData } from '@/types/server'
import { getAlertSound } from '@/config/sounds'

export interface Alert extends AlertData {
  type: 'follow' | 'sub' | 'resub' | 'sub_gift' | 'community_sub_gift' | 'bits_badge_tier' | 'cheer' | 'raid' | 'tip' | 'community_gift_bundle'
  username?: string
  duration: number
  soundFile?: string
  tier?: 'Tier 1' | 'Tier 2' | 'Tier 3'
  months?: number
}

export type QueueStatus = 'processing' | 'paused' | 'bypassed' | 'idle'

export interface AlertQueueState {
  currentAlert: Alert | null
  alertQueue: Alert[]
  visibleQueue: Alert[]
  queueDepth: number
  isProcessing: boolean
  queueStatus: QueueStatus
  alertHistory: Alert[]
}

export interface AlertQueueConfig {
  maxVisibleQueue?: number // How many alerts to show in stack (default: 4)
  autoProcess?: boolean // Auto-process queue (default: true)
  soundEnabled?: boolean // DASHBOARD UI: Global sound on/off toggle
  isPaused?: boolean // DASHBOARD UI: Pause button with visual state indicator
  bypassMode?: boolean // DASHBOARD UI: Bypass toggle (emergency skip all)
}

// DASHBOARD UI NEEDED: History viewer with filters and clear button
const MAX_HISTORY = 20 // Keep last 20 processed alerts

export function useAlertQueue(config: AlertQueueConfig = {}) {
  const {
    maxVisibleQueue = 4,
    autoProcess = true,
    soundEnabled = true,
    isPaused = false,
    bypassMode = false,
  } = config

  // Get state from store
  const alerts = useRealtimeStore((state) => state.alerts)
  const addAlertToStore = useRealtimeStore((state) => state.addAlert)
  const removeCurrentAlert = useRealtimeStore((state) => state.removeCurrentAlert)
  const clearAlertQueueStore = useRealtimeStore((state) => state.clearAlertQueue)
  const setAlertAnimating = useRealtimeStore((state) => state.setAlertAnimating)
  const setPausedState = useRealtimeStore((state) => state.setPausedState)

  // Local state for history and processing timeout
  const [alertHistory, setAlertHistory] = useState<Alert[]>([])
  const processTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined)

  // Transform store alerts to include additional properties
  const alertQueue = useMemo(() => {
    return alerts.queue.map(alert => {
      const soundFile = getAlertSound(alert)
      if (!soundFile) {
        console.warn('[Alerts] No sound mapped for alert:', alert.type, alert)
      }
      return {
        ...alert,
        username: alert.user_name,
        soundFile,
      } as Alert
    })
  }, [alerts.queue])

  const currentAlert = useMemo(() => {
    if (!alerts.currentAlert) return null

    const soundFile = getAlertSound(alerts.currentAlert)
    if (!soundFile) {
      console.warn('[Alerts] No sound mapped for current alert:', alerts.currentAlert.type, alerts.currentAlert)
    }

    return {
      ...alerts.currentAlert,
      username: alerts.currentAlert.user_name,
      soundFile,
    } as Alert
  }, [alerts.currentAlert])

  const isProcessing = alerts.isAnimating

  // Get visible portion of queue for stack display
  const visibleQueue = alertQueue.slice(0, maxVisibleQueue)
  const queueDepth = alertQueue.length

  // Determine current queue status
  const queueStatus: QueueStatus = bypassMode
    ? 'bypassed'
    : alerts.isPaused
      ? 'paused'
      : isProcessing
        ? 'processing'
        : 'idle'

  // Update paused state in store when config changes
  useEffect(() => {
    setPausedState(isPaused)
  }, [isPaused, setPausedState])


  // Add alert to queue
  const addAlert = useCallback((alertData: Omit<Alert, 'id' | 'timestamp' | 'duration' | 'soundFile'>) => {
    // Skip entirely if bypass mode is on
    if (bypassMode) return

    // Convert to store format
    const storeAlert: AlertData = {
      id: `alert-${Date.now()}-${Math.random()}`,
      type: alertData.type,
      message: alertData.message || '',
      user_name: alertData.username,
      amount: alertData.amount,
      timestamp: new Date().toISOString(),
    }

    // Add to store (FIFO queue)
    addAlertToStore(storeAlert)
  }, [bypassMode, addAlertToStore])

  // Process next alert in queue
  const processNext = useCallback(() => {
    // Guard against processing if already have current alert
    if (alerts.currentAlert) {
      return
    }

    if (alerts.queue.length === 0) {
      removeCurrentAlert()
      setAlertAnimating(false)
      return
    }

    // Clear any existing timeout
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
      processTimeoutRef.current = undefined
    }

    // Get first alert from queue and set as current
    const nextAlert = alerts.queue[0]

    // Update store to move alert from queue to current
    useRealtimeStore.setState((state) => ({
      alerts: {
        ...state.alerts,
        currentAlert: nextAlert,
        queue: state.alerts.queue.slice(1),
      },
    }))

    setAlertAnimating(true)
  }, [alerts.queue, alerts.currentAlert, removeCurrentAlert, setAlertAnimating])

  // Handle alert completion (called by Alert component)
  const onAlertComplete = useCallback(() => {
    if (!currentAlert) return

    // Clear any existing timeout
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
      processTimeoutRef.current = undefined
    }

    // Add to history when alert completes
    const historyAlert = {
      ...currentAlert,
      username: currentAlert.username,
      duration: currentAlert.duration,
      soundFile: undefined,
    } as Alert

    setAlertHistory(prev => [historyAlert, ...prev].slice(0, MAX_HISTORY))

    // Release any pending timeline event with the same ID
    const releaseTimelineEvent = useRealtimeStore.getState().releaseTimelineEvent
    releaseTimelineEvent(currentAlert.id)

    removeCurrentAlert()
    setAlertAnimating(false)
  }, [currentAlert, removeCurrentAlert, setAlertAnimating])

  // Clear current alert (for manual control)
  const clearCurrent = useCallback(() => {
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
    }
    removeCurrentAlert()
    setAlertAnimating(false)
  }, [removeCurrentAlert, setAlertAnimating])

  // Clear entire queue
  const clearQueue = useCallback(() => {
    clearAlertQueueStore()
    clearCurrent()
  }, [clearAlertQueueStore, clearCurrent])

  // Auto-process queue when not processing and queue has items
  useEffect(() => {
    if (!autoProcess) return
    if (alerts.isPaused) return // Don't process when paused
    if (isProcessing || alerts.queue.length === 0) return
    if (alerts.currentAlert) return // Already have a current alert

    // Small delay to allow for animations
    const processTimer = setTimeout(() => {
      processNext()
    }, 100)

    return () => clearTimeout(processTimer)
  }, [autoProcess, alerts.isPaused, isProcessing, alerts.queue.length, alerts.currentAlert, processNext])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (processTimeoutRef.current) {
        clearTimeout(processTimeoutRef.current)
      }
    }
  }, [])

  return {
    // State
    currentAlert,
    alertQueue,
    visibleQueue,
    queueDepth,
    isProcessing,
    queueStatus,
    alertHistory,

    // Control flags
    isPaused: alerts.isPaused,
    isBypassed: bypassMode,
    soundEnabled,

    // Actions
    addAlert,
    processNext,
    clearCurrent,
    clearQueue,
    onAlertComplete,
  }
}
