import { createFileRoute } from '@tanstack/react-router'

import { Alert } from '@/components/shared/alert'
import { useAlertQueue } from '@/hooks/use-alerts'

function AudioOnly() {
  const { currentAlert, onAlertComplete } = useAlertQueue({ soundEnabled: true })

  return <Alert currentAlert={currentAlert} onComplete={onAlertComplete} soundEnabled={true} />
}

export const Route = createFileRoute('/audio')({
  component: AudioOnly,
})
