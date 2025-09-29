import { useAlertSound } from '@/hooks/use-alert-sound'
import type { Alert as AlertType } from '@/hooks/use-alerts'

interface AlertProps {
  currentAlert: AlertType | null
  onComplete?: () => void
  soundEnabled?: boolean
  volume?: number
}

export const Alert = ({
  currentAlert,
  onComplete,
  soundEnabled = true,
  volume = 0.2,
}: AlertProps) => {
  useAlertSound(currentAlert, {
    enabled: soundEnabled,
    volume,
    onComplete,
  })

  return null
}
