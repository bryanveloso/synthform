import { useEffect, useRef, useState } from 'react'
import { getAlertSound } from '@/config/sounds'
import { getPreloadedAudio } from '@/lib/audio-preloader'
import type { Alert } from './use-alerts'

interface UseAlertSoundOptions {
  enabled?: boolean
  volume?: number
  onComplete?: () => void
  fallbackDuration?: number
}

interface UseAlertSoundReturn {
  isPlaying: boolean
  error: string | null
}

export function useAlertSound(
  alert: Alert | null,
  options: UseAlertSoundOptions = {},
): UseAlertSoundReturn {
  const { enabled = true, volume = 0.2, onComplete, fallbackDuration = 10000 } = options

  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const completionTimerRef = useRef<NodeJS.Timeout | null>(null)
  const endedHandlerRef = useRef<(() => void) | null>(null)
  const activeAlertIdRef = useRef<string | null>(null)

  useEffect(() => {
    // Clear any existing completion timer
    if (completionTimerRef.current) {
      clearTimeout(completionTimerRef.current)
      completionTimerRef.current = null
    }

    // Clean up previous audio if it exists
    if (audioRef.current) {
      audioRef.current.pause()
      if (endedHandlerRef.current) {
        audioRef.current.removeEventListener('ended', endedHandlerRef.current)
        endedHandlerRef.current = null
      }
      audioRef.current.src = ''
      audioRef.current.load()
      audioRef.current = null
    }

    // Reset state
    setIsPlaying(false)
    setError(null)

    // Process alert (with or without sound)
    if (alert) {
      activeAlertIdRef.current = alert.id
      const soundFile = enabled ? getAlertSound(alert) : null

      if (soundFile && enabled) {
        // Use preloaded audio for instant playback (gets a cloned element)
        const preloadedAudio = getPreloadedAudio(soundFile)

        if (preloadedAudio) {
          audioRef.current = preloadedAudio
          audioRef.current.volume = volume
        } else {
          // Fallback to on-demand loading if not preloaded
          audioRef.current = new Audio(soundFile)
          audioRef.current.volume = volume
        }

        // Set up completion handlers
        const endedHandler = () => {
          // Ignore stale events from previous alerts
          if (activeAlertIdRef.current !== alert.id) {
            return
          }

          // Clear the fallback timer since audio ended naturally
          if (completionTimerRef.current) {
            clearTimeout(completionTimerRef.current)
            completionTimerRef.current = null
          }
          setIsPlaying(false)
          onComplete?.()
        }
        endedHandlerRef.current = endedHandler
        audioRef.current.addEventListener('ended', endedHandler)

        // Play the audio and handle errors
        audioRef.current
          .play()
          .then(() => {
            setIsPlaying(true)

            // Set fallback timer in case 'ended' doesn't fire
            const duration = alert.duration || fallbackDuration
            completionTimerRef.current = setTimeout(() => {
              setIsPlaying(false)
              onComplete?.()
            }, duration)
          })
          .catch((err) => {
            const errorMsg = `Failed to play alert sound for ${alert.type}: ${err.message}`
            console.warn(errorMsg)
            setError(errorMsg)
            setIsPlaying(false)
            // Still call onComplete if audio fails
            onComplete?.()
          })
      } else {
        // No sound file or sound disabled, use duration timer
        const duration = alert.duration || fallbackDuration
        completionTimerRef.current = setTimeout(() => {
          onComplete?.()
        }, duration)
      }
    } else {
      activeAlertIdRef.current = null
    }

    // Cleanup on unmount or when dependencies change
    return () => {
      if (completionTimerRef.current) {
        clearTimeout(completionTimerRef.current)
        completionTimerRef.current = null
      }
      if (audioRef.current) {
        audioRef.current.pause()
        if (endedHandlerRef.current) {
          audioRef.current.removeEventListener('ended', endedHandlerRef.current)
          endedHandlerRef.current = null
        }
        audioRef.current.src = ''
        audioRef.current.load()
        audioRef.current = null
      }
      setIsPlaying(false)
    }
  }, [alert, enabled, volume, onComplete, fallbackDuration])

  return {
    isPlaying,
    error,
  }
}
