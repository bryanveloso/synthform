import { useAlertQueue } from '@/hooks/use-alerts'
import { useAlertSound } from '@/hooks/use-alert-sound'

interface AlertProps {
  onComplete?: () => void
  soundEnabled?: boolean
  volume?: number
}

export const Alert = ({ onComplete, soundEnabled = true, volume = 0.3 }: AlertProps = {}) => {
  const { currentAlert } = useAlertQueue()

  // Use the reusable sound hook
  const { isPlaying, error } = useAlertSound(currentAlert, {
    enabled: soundEnabled,
    volume,
    onComplete,
    fallbackDuration: 3000,
  })

  // Log status for now to avoid unused variable warnings
  if (error) {
    console.error('Alert sound error:', error)
  }
  if (isPlaying) {
    console.log('Alert sound playing')
  }

  // Component is ready for visual display logic to be added here
  // For now, it just handles sound through the hook

  return null
}
