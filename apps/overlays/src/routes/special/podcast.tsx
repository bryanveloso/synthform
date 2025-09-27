import { createFileRoute } from '@tanstack/react-router'

import { Podcast } from '@/components/special/podcast'

export const Route = createFileRoute('/special/podcast')({
  component: Podcast,
})
