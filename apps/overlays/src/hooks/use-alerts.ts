import { useState, useCallback, useEffect, useRef } from 'react'
import { alertSoundConfig } from '@/config/alert-sounds'

export interface Alert {
  id: string
  type: 'follow' | 'subscription' | 'resub' | 'gift' | 'cheer' | 'raid' | 'tip'
  username: string
  message?: string
  amount?: number
  tier?: 'Tier 1' | 'Tier 2' | 'Tier 3'
  months?: number // For resubs
  duration: number
  priority: number
  timestamp: Date
  soundFile?: string
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
  soundEnabled?: boolean
  priorityMap?: Record<Alert['type'], number>
  isPaused?: boolean // Pause processing but keep queueing
  bypassMode?: boolean // Skip all alerts entirely
}

const DEFAULT_PRIORITY_MAP: Record<Alert['type'], number> = {
  gift: 5,      // Highest - most generous
  tip: 4,       // Direct support
  resub: 3,     // Loyal supporters
  subscription: 3,
  cheer: 2,     // Bits support
  follow: 1,    // New viewers
  raid: 0,      // Lowest - already getting attention
}

const DEFAULT_DURATIONS: Record<Alert['type'], number> = {
  follow: 3000,
  subscription: 5000,
  resub: 6000,
  gift: 6000,
  cheer: 4000,
  raid: 7000,
  tip: 5000,
}

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

  const [alertQueue, setAlertQueue] = useState<Alert[]>([])
  const [currentAlert, setCurrentAlert] = useState<Alert | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [alertHistory, setAlertHistory] = useState<Alert[]>([])
  const processTimeoutRef = useRef<NodeJS.Timeout | undefined>()

  // Get visible portion of queue for stack display
  const visibleQueue = alertQueue.slice(0, maxVisibleQueue)
  const queueDepth = alertQueue.length

  // Determine current queue status
  const queueStatus: QueueStatus = bypassMode
    ? 'bypassed'
    : isPaused
      ? 'paused'
      : isProcessing
        ? 'processing'
        : 'idle'

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

  // Add alert to queue with priority insertion
  const addAlert = useCallback((alertData: Omit<Alert, 'id' | 'priority' | 'timestamp' | 'duration' | 'soundFile'>) => {
    // Skip entirely if bypass mode is on
    if (bypassMode) return

    const alert: Alert = {
      ...alertData,
      id: `alert-${Date.now()}-${Math.random()}`,
      priority: priorityMap[alertData.type],
      timestamp: new Date(),
      duration: DEFAULT_DURATIONS[alertData.type],
    }

    // Select appropriate sound file
    alert.soundFile = selectSoundFile(alert)

    setAlertQueue(prev => {
      // Insert based on priority (higher priority first)
      const newQueue = [...prev]
      const insertIndex = newQueue.findIndex(a => a.priority < alert.priority)

      if (insertIndex === -1) {
        // Lowest priority or empty queue
        newQueue.push(alert)
      } else {
        // Insert before lower priority alerts
        newQueue.splice(insertIndex, 0, alert)
      }

      return newQueue
    })
  }, [priorityMap, selectSoundFile, bypassMode])

  // Process next alert in queue
  const processNext = useCallback(() => {
    if (alertQueue.length === 0) {
      setCurrentAlert(null)
      setIsProcessing(false)
      return
    }

    const nextAlert = alertQueue[0]
    setCurrentAlert(nextAlert)
    setAlertQueue(prev => prev.slice(1))
    setIsProcessing(true)

    // Clear any existing timeout
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
    }

    // Schedule completion
    processTimeoutRef.current = setTimeout(() => {
      // Add to history when alert completes
      setAlertHistory(prev => [nextAlert, ...prev].slice(0, MAX_HISTORY))
      setCurrentAlert(null)
      setIsProcessing(false)
    }, nextAlert.duration)
  }, [alertQueue])

  // Clear current alert (for manual control)
  const clearCurrent = useCallback(() => {
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current)
    }
    setCurrentAlert(null)
    setIsProcessing(false)
  }, [])

  // Clear entire queue
  const clearQueue = useCallback(() => {
    setAlertQueue([])
    clearCurrent()
  }, [clearCurrent])

  // Auto-process queue when not processing and queue has items
  useEffect(() => {
    if (!autoProcess) return
    if (isPaused) return // Don't process when paused
    if (isProcessing || alertQueue.length === 0) return

    // Small delay to allow for animations
    const processTimer = setTimeout(() => {
      processNext()
    }, 100)

    return () => clearTimeout(processTimer)
  }, [autoProcess, isPaused, isProcessing, alertQueue.length, processNext])

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
    isPaused,
    isBypassed: bypassMode,

    // Actions
    addAlert,
    processNext,
    clearCurrent,
    clearQueue,
  }
}
