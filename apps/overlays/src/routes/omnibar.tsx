import { createFileRoute } from '@tanstack/react-router'
import { Omnibar } from '@/components/omnibar'

export const Route = createFileRoute('/omnibar')({
  component: RouteComponent,
})

function RouteComponent() {
  return <Omnibar />
}
