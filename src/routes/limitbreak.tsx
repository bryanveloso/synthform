import { LimitBreak } from '@/components/omnibar/limitbreak'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/limitbreak')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div><LimitBreak /></div>
}
