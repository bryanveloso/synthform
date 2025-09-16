import { Canvas } from '@/components/ui/canvas'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/(full)/start')({
  component: RouteComponent,
})

function RouteComponent() {
  return (
    <Canvas>
      <div className="flex items-center justify-center w-full h-full backdrop-blur">
        <div className="aspect-video w-7xl bg-red-700 rounded-lg shadow-xl/50"></div>
      </div>
    </Canvas>
  )
}
