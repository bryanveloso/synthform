import { useCallback, useState, useEffect } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import type { Milestone } from '@/types/campaign'

/**
 * Hook for accessing and managing campaign data.
 * Campaign data comes through WebSocket messages, no API fetching needed.
 */
export function useCampaign() {
  // Track current stream duration with ticker - MUST be before other hooks
  const [currentStreamDuration, setCurrentStreamDuration] = useState(0)

  // Store selectors - data comes from WebSocket
  const campaign = useRealtimeStore((state) => state.campaign)
  const isConnected = useRealtimeStore((state) => state.isConnected)

  // Computed: Basic campaign info
  const isActive = campaign?.is_active ?? false
  const hasTimer = campaign?.timer_mode ?? false
  const name = campaign?.name ?? ''
  const description = campaign?.description ?? ''

  // Computed: Metrics
  const totalSubs = campaign?.metric?.total_subs ?? 0
  const totalResubs = campaign?.metric?.total_resubs ?? 0
  const totalBits = campaign?.metric?.total_bits ?? 0
  const timerSeconds = campaign?.metric?.timer_seconds_remaining ?? 0
  const totalDurationFromCompleted = campaign?.metric?.total_duration ?? 0
  const streamStartedAt = campaign?.metric?.stream_started_at ?? null

  // Combined count for display and milestone tracking
  const totalSubsWithResubs = totalSubs + totalResubs

  // Update current stream duration every second
  useEffect(() => {
    if (!streamStartedAt) {
      setCurrentStreamDuration(0)
      return
    }

    // Calculate initial duration
    const startTime = new Date(streamStartedAt).getTime()
    const updateDuration = () => {
      const duration = Math.floor((Date.now() - startTime) / 1000)
      setCurrentStreamDuration(duration)
    }

    // Set initial value
    updateDuration()

    // Update every second
    const interval = setInterval(updateDuration, 1000)

    return () => clearInterval(interval)
  }, [streamStartedAt])

  // Total duration includes completed sessions + current stream
  const totalDuration = totalDurationFromCompleted + currentStreamDuration

  // Computed: Timer state
  const timerStarted = campaign?.metric?.timer_started_at != null
  const timerPaused = campaign?.metric?.timer_paused_at != null
  const timerRunning = timerStarted && !timerPaused && timerSeconds > 0
  const timerExpired = timerStarted && timerSeconds <= 0

  // Computed: Timer configuration
  const secondsPerSub = campaign?.seconds_per_sub ?? 0
  const secondsPerTier2 = campaign?.seconds_per_tier2 ?? 0
  const secondsPerTier3 = campaign?.seconds_per_tier3 ?? 0
  const maxSeconds = campaign?.max_timer_seconds ?? null
  const isAtCap = maxSeconds != null && timerSeconds >= maxSeconds

  // Computed: Milestones
  const milestones = campaign?.milestones ?? []
  const unlockedMilestones = milestones.filter((m) => m.is_unlocked)
  const lockedMilestones = milestones.filter((m) => !m.is_unlocked)
  const nextMilestone = lockedMilestones.sort((a, b) => a.threshold - b.threshold)[0] as
    | Milestone
    | undefined

  // Computed: Progress (based on combined total for milestones)
  const progress = nextMilestone
    ? Math.min(100, (totalSubsWithResubs / nextMilestone.threshold) * 100)
    : 100 // All milestones complete

  const subsToNextMilestone = nextMilestone
    ? Math.max(0, nextMilestone.threshold - totalSubsWithResubs)
    : 0

  const milestonesUnlocked = unlockedMilestones.length
  const milestonesTotal = milestones.length
  const milestonesProgress = milestonesTotal > 0 ? (milestonesUnlocked / milestonesTotal) * 100 : 0

  // Helper: Calculate time to add for an event
  const calculateTimeForEvent = useCallback(
    (type: 'sub' | 'gift' | 'bits', tier: 1 | 2 | 3 = 1, amount: number = 1): number => {
      if (!campaign) return 0

      switch (type) {
        case 'sub':
          if (tier === 3) return secondsPerTier3
          if (tier === 2) return secondsPerTier2
          return secondsPerSub
        case 'gift':
          // Gifts are always tier 1 * amount
          return secondsPerSub * amount
        case 'bits':
          // Could add bits calculation if configured
          return 0
        default:
          return 0
      }
    },
    [campaign, secondsPerSub, secondsPerTier2, secondsPerTier3],
  )

  // Helper: Format timer display
  const formatTimerDisplay = useCallback((seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }, [])

  // Helper: Format duration display (shows hours and minutes)
  const formatDurationDisplay = useCallback((seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }, [])

  return {
    // Core data
    campaign,
    isConnected,

    // Campaign info
    isActive,
    name,
    description,

    // Metrics
    totalSubs,
    totalResubs,
    totalSubsWithResubs,
    totalBits,
    totalDuration,
    streamStartedAt,

    // Timer state
    hasTimer,
    timerSeconds,
    timerStarted,
    timerPaused,
    timerRunning,
    timerExpired,
    isAtCap,

    // Timer config
    secondsPerSub,
    secondsPerTier2,
    secondsPerTier3,
    maxSeconds,

    // Milestones
    milestones,
    unlockedMilestones,
    lockedMilestones,
    nextMilestone,
    milestonesUnlocked,
    milestonesTotal,
    milestonesProgress,

    // Progress
    progress,
    subsToNextMilestone,

    // Helpers
    calculateTimeForEvent,
    formatTimerDisplay,
    formatDurationDisplay,
  }
}
