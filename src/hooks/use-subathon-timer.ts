import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useCampaign } from './use-campaign'
import type { Campaign, CampaignMetric } from '@/types/campaign'

interface UseSubathonTimerOptions {
  // Update frequency for the countdown (in ms)
  tickInterval?: number
  // Format function for time display
  formatTime?: (hours: number, minutes: number, seconds: number) => string
  // Optional: provide campaign data externally (to prevent duplicate fetching)
  campaign?: Campaign | null
  metric?: CampaignMetric | null
  timerRunning?: boolean
}

export function useSubathonTimer(options: UseSubathonTimerOptions = {}) {
  const { tickInterval = 1000, formatTime } = options

  const [timeRemaining, setTimeRemaining] = useState<number>(0)
  const [formattedTime, setFormattedTime] = useState<string>('00:00:00')
  const tickIntervalRef = useRef<NodeJS.Timeout | undefined>(undefined)
  const endTimeRef = useRef<Date | null>(null)

  // Get campaign data from hook or use provided data
  const ownData = useCampaign()

  // Use provided data or hook data
  const campaign = options.campaign ?? ownData.campaign
  const metric = options.metric ?? ownData.campaign?.metric ?? null
  const timerRunning = options.timerRunning ?? ownData.timerRunning
  const isConnected = ownData.isConnected

  // Default time formatter
  const defaultFormatTime = useCallback((hours: number, minutes: number, seconds: number) => {
    const pad = (n: number) => n.toString().padStart(2, '0')
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
  }, [])

  // Memoize the formatter to prevent recreating it
  const formatter = useMemo(
    () => formatTime || defaultFormatTime,
    [formatTime, defaultFormatTime]
  )

  // Calculate end time from seconds remaining (separate from interval management)
  useEffect(() => {
    if (metric && metric.timer_seconds_remaining > 0 && timerRunning) {
      endTimeRef.current = new Date(Date.now() + metric.timer_seconds_remaining * 1000)
    } else if (!timerRunning) {
      endTimeRef.current = null
    }
  }, [metric, timerRunning])

  // Manage countdown interval
  useEffect(() => {
    const timerSeconds = metric?.timer_seconds_remaining || 0

    if (!timerRunning || !endTimeRef.current) {
      setTimeRemaining(timerSeconds)
      if (tickIntervalRef.current) {
        clearInterval(tickIntervalRef.current)
        tickIntervalRef.current = undefined
      }
      return
    }

    const updateTimer = () => {
      if (!endTimeRef.current) return

      const now = Date.now()
      const diff = endTimeRef.current.getTime() - now
      const secondsLeft = Math.max(0, Math.floor(diff / 1000))

      setTimeRemaining(secondsLeft)

      if (secondsLeft === 0) {
        endTimeRef.current = null
        if (tickIntervalRef.current) {
          clearInterval(tickIntervalRef.current)
          tickIntervalRef.current = undefined
        }
      }
    }

    updateTimer()
    tickIntervalRef.current = setInterval(updateTimer, tickInterval)

    return () => {
      if (tickIntervalRef.current) {
        clearInterval(tickIntervalRef.current)
        tickIntervalRef.current = undefined
      }
    }
  }, [timerRunning, tickInterval, metric?.timer_seconds_remaining])

  // Format time for display
  useEffect(() => {
    const hours = Math.floor(timeRemaining / 3600)
    const minutes = Math.floor((timeRemaining % 3600) / 60)
    const seconds = timeRemaining % 60

    setFormattedTime(formatter(hours, minutes, seconds))
  }, [timeRemaining, formatter])

  // Calculate time added from events
  const calculateTimeAdded = useCallback(
    (eventType: string, tier?: number, amount?: number): number => {
      if (!campaign) return 0

      switch (eventType) {
        case 'subscription':
          if (tier === 3) return campaign.seconds_per_tier3
          if (tier === 2) return campaign.seconds_per_tier2
          return campaign.seconds_per_sub
        case 'gift':
          return campaign.seconds_per_sub * (amount || 1)
        case 'bits':
          // Could add bits configuration if needed
          return 0
        default:
          return 0
      }
    },
    [campaign]
  )

  // Progress percentage (for visual indicators)
  const progressPercentage = useMemo(() => {
    if (!campaign?.max_timer_seconds || !metric?.timer_seconds_remaining) return 0
    return Math.min(100, (metric.timer_seconds_remaining / campaign.max_timer_seconds) * 100)
  }, [campaign, metric])

  // Time until cap
  const secondsUntilCap = useMemo(() => {
    if (!campaign?.max_timer_seconds || !metric?.timer_seconds_remaining) return null
    return Math.max(0, campaign.max_timer_seconds - metric.timer_seconds_remaining)
  }, [campaign, metric])

  // Helper to format seconds for display
  const formatSeconds = useCallback((seconds: number): string => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }, [])

  // Check if timer is near expiration
  const isExpiringSoon = useMemo(() => {
    return timeRemaining > 0 && timeRemaining < 300 // Less than 5 minutes
  }, [timeRemaining])

  // Check if timer is at cap
  const isAtCap = useMemo(() => {
    if (!campaign?.max_timer_seconds || !metric?.timer_seconds_remaining) return false
    return metric.timer_seconds_remaining >= campaign.max_timer_seconds
  }, [campaign, metric])

  return {
    // Core timer data
    timeRemaining,
    formattedTime,
    timerRunning,

    // Campaign data
    campaign,
    metric,
    isConnected,

    // Timer state
    isExpiringSoon,
    isAtCap,
    progressPercentage,
    secondsUntilCap,

    // Configuration
    secondsPerSub: campaign?.seconds_per_sub || 0,
    secondsPerTier2: campaign?.seconds_per_tier2 || 0,
    secondsPerTier3: campaign?.seconds_per_tier3 || 0,
    maxTimerSeconds: campaign?.max_timer_seconds || null,

    // Methods
    calculateTimeAdded,
    formatSeconds,

    // Raw values for custom formatting
    hours: Math.floor(timeRemaining / 3600),
    minutes: Math.floor((timeRemaining % 3600) / 60),
    seconds: timeRemaining % 60,
  }
}
