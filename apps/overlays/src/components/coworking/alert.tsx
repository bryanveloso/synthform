import { useEffect, useRef } from 'react'
import { useAlertQueue } from '@/hooks/use-alerts'
import { getAlertSound } from '@/config/sounds'

// Volume configuration (0.0 to 1.0)
// You can move this to a config file or pass as prop
const ALERT_VOLUME = 0.5 // 50% volume

interface AlertProps {
  onComplete?: () => void
  soundEnabled?: boolean
}

export const Alert = ({ onComplete, soundEnabled = true }: AlertProps = {}) => {
  const { currentAlert } = useAlertQueue()
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

    // Play sound for new alert
    if (currentAlert) {
      const soundFile = soundEnabled ? getAlertSound(
        currentAlert.type,
        currentAlert.amount,
        currentAlert.tier
      ) : undefined

      if (soundFile) {
        audioRef.current = new Audio(soundFile)
        audioRef.current.volume = ALERT_VOLUME

        // Set up completion handlers
        audioRef.current.addEventListener('ended', () => {
          onComplete?.()
        })

        // Play the audio and handle errors
        audioRef.current.play().then(() => {
          // Audio started playing successfully
          // Set fallback timer in case 'ended' doesn't fire
          const duration = currentAlert.duration || 3000
          completionTimerRef.current = setTimeout(() => {
            onComplete?.()
          }, duration)
        }).catch(err => {
          console.warn(`Failed to play alert sound for ${currentAlert.type}:`, err)
          // Still call onComplete if audio fails
          onComplete?.()
        })
      } else {
        // No sound file, use minimum duration for visual alerts
        const duration = currentAlert.duration || 3000
        completionTimerRef.current = setTimeout(() => {
          onComplete?.()
        }, duration)
      }
    }

    // Cleanup on unmount
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
    }
  }, [currentAlert, onComplete, soundEnabled])

  return null
}
