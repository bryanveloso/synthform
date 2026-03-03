import { createFileRoute } from '@tanstack/react-router'

import { Coworking } from '@/components/coworking'

export const Route = createFileRoute('/(full)/coworking')({
  component: Coworking,
})
