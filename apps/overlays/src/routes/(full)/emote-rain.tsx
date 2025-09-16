import { createFileRoute } from '@tanstack/react-router'
import { Canvas } from '@/components/ui/canvas'
import { EmoteRain } from '@/components/effects/emote-rain'

export const Route = createFileRoute('/(full)/emote-rain')({
  component: RouteComponent,
})

function RouteComponent() {
  return (
    <Canvas>
      <EmoteRain />
    </Canvas>
  )
}