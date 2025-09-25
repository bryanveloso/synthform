import { createFileRoute } from '@tanstack/react-router'

import { Omnibar } from '@/components/omnibar'

export const Route = createFileRoute('/(full)/omnibar')({
  component: Omnibar,
})
