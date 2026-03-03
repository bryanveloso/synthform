import { Podcast } from '@/components/special/podcast'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/special/podcast')({
  component: Podcast,
})
