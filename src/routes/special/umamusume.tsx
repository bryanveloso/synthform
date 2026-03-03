import { createFileRoute } from '@tanstack/react-router'

import { Umamusume } from '@/components/special/umamusume'

export const Route = createFileRoute('/special/umamusume')({
  component: Umamusume,
})
