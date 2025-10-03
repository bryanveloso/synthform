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

  useEffect(() => {
    // Clear any existing completion timer
    if (completionTimerRef.current) {
      clearTimeout(completionTimerRef.current)
      completionTimerRef.current = null
    }

    // Clean up previous audio if it exists
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current.load()
      audioRef.current = null
    }

    // Reset state
    setIsPlaying(false)
    setError(null)

    // Process alert (with or without sound)
    if (alert) {
      const soundFile = enabled ? getAlertSound(alert) : null

      if (soundFile && enabled) {
        // Use preloaded audio for instant playback
        const preloadedAudio = getPreloadedAudio(soundFile)

        if (preloadedAudio) {
          audioRef.current = preloadedAudio
          audioRef.current.volume = volume
          // Reset playback position for cached audio
          audioRef.current.currentTime = 0
        } else {
          // Fallback to on-demand loading if not preloaded
          audioRef.current = new Audio(soundFile)
          audioRef.current.volume = volume
        }

        // Set up completion handlers
        audioRef.current.addEventListener('ended', () => {
          // Clear the fallback timer since audio ended naturally
          if (completionTimerRef.current) {
            clearTimeout(completionTimerRef.current)
            completionTimerRef.current = null
          }
          setIsPlaying(false)
          onComplete?.()
        })

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
    }

    // Cleanup on unmount or when dependencies change
    return () => {
      if (completionTimerRef.current) {
        clearTimeout(completionTimerRef.current)
        completionTimerRef.current = null
      }
      if (audioRef.current) {
        audioRef.current.pause()
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
