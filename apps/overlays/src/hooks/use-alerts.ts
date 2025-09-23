import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import { alertSoundConfig } from '@/config/alert-sounds'
import type { AlertData } from '@/types/server'

export interface Alert extends AlertData {
  type: 'follow' | 'subscription' | 'resub' | 'gift' | 'cheer' | 'raid' | 'tip'
  username?: string
  duration: number
  priority: number
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
  priorityMap?: Record<Alert['type'], number> // DASHBOARD UI: Priority editor with drag-drop reordering
  isPaused?: boolean // DASHBOARD UI: Pause button with visual state indicator
  bypassMode?: boolean // DASHBOARD UI: Bypass toggle (emergency skip all)
}

// DASHBOARD UI NEEDED: Priority editor with visual preview of queue order
const DEFAULT_PRIORITY_MAP: Record<Alert['type'], number> = {
  gift: 5,      // Highest - most generous
  tip: 4,       // Direct support
  resub: 3,     // Loyal supporters
  subscription: 3,
  cheer: 2,     // Bits support
  follow: 1,    // New viewers
  raid: 0,      // Lowest - already getting attention
}

// DASHBOARD UI NEEDED: Duration slider per event type (1-10 seconds)
const DEFAULT_DURATIONS: Record<Alert['type'], number> = {
  follow: 3000,
  subscription: 5000,
  resub: 6000,
  gift: 6000,
  cheer: 4000,
  raid: 7000,
  tip: 5000,
}

// DASHBOARD UI NEEDED: History viewer with filters and clear button
const MAX_HISTORY = 20 // Keep last 20 processed alerts

export function useAlertQueue(config: AlertQueueConfig = {}) {
  const {
    maxVisibleQueue = 4,
    autoProcess = true,
    soundEnabled = true,
    priorityMap = DEFAULT_PRIORITY_MAP,
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
    return alerts.queue.map(alert => ({
      ...alert,
      username: alert.user_name,
      duration: DEFAULT_DURATIONS[alert.type as Alert['type']] || 5000,
      priority: priorityMap[alert.type as Alert['type']] || 0,
      soundFile: undefined,
    } as Alert))
  }, [alerts.queue, priorityMap])

  const currentAlert = useMemo(() => {
    if (!alerts.currentAlert) return null
    return {
      ...alerts.currentAlert,
      username: alerts.currentAlert.user_name,
      duration: DEFAULT_DURATIONS[alerts.currentAlert.type as Alert['type']] || 5000,
      priority: priorityMap[alerts.currentAlert.type as Alert['type']] || 0,
      soundFile: undefined,
    } as Alert
  }, [alerts.currentAlert, priorityMap])

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

  // Select sound file based on event magnitude
  const selectSoundFile = useCallback((alert: Alert): string | undefined => {
    if (!soundEnabled) return undefined

    const config = alertSoundConfig[alert.type]
    if (!config) return undefined

    // Handle subscription tiers
    if (alert.type === 'subscription' || alert.type === 'resub') {
      const tierNum = alert.tier === 'Tier 3' ? 3 : alert.tier === 'Tier 2' ? 2 : 1
      return config.sounds[tierNum] || config.sounds[1]
    }

    // Handle amount-based events (gifts, cheers, tips)
    if (alert.amount && config.sounds) {
      const thresholds = Object.keys(config.sounds)
        .map(Number)
        .sort((a, b) => b - a)

      for (const threshold of thresholds) {
        if (alert.amount >= threshold) {
          return config.sounds[threshold]
        }
      }
    }

    // Default sound for the event type
    return config.sounds?.[1] || config.defaultSound
  }, [soundEnabled])

  // Add alert to queue
  const addAlert = useCallback((alertData: Omit<Alert, 'id' | 'priority' | 'timestamp' | 'duration' | 'soundFile'>) => {
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

    // Add to store (store handles priority queue insertion)
    addAlertToStore(storeAlert)
  }, [bypassMode, addAlertToStore])

  // Process next alert in queue
  const processNext = useCallback(() => {
    if (alerts.queue.length === 0) {
      removeCurrentAlert()
      setAlertAnimating(false)
      return
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

    // Clear any existing timeout
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
    }

    const duration = DEFAULT_DURATIONS[nextAlert.type as Alert['type']] || 5000

    // Schedule completion
    processTimeoutRef.current = setTimeout(() => {
      // Add to history when alert completes
      const historyAlert = {
        ...nextAlert,
        username: nextAlert.user_name,
        duration,
        priority: priorityMap[nextAlert.type as Alert['type']] || 0,
        soundFile: undefined,
      } as Alert

      setAlertHistory(prev => [historyAlert, ...prev].slice(0, MAX_HISTORY))
      removeCurrentAlert()
      setAlertAnimating(false)
    }, duration)
  }, [alerts.queue, removeCurrentAlert, setAlertAnimating, priorityMap])

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

    // Actions
    addAlert,
    processNext,
    clearCurrent,
    clearQueue,
  }
}
