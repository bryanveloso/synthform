import { createFileRoute } from '@tanstack/react-router'

import { Canvas } from '@/components/ui/canvas'
import { useTimeComponents } from '@/hooks/use-time'

export const Route = createFileRoute('/(full)/intro')({
  component: RouteComponent,
})

function RouteComponent() {
  // Example: Custom time display with individual components
  const { day, dayName, monthName, year, hours, minutes } = useTimeComponents()

  return (
    <Canvas>
      <div className="from-shark-880 to-shark-960 flex h-full w-full items-center justify-center bg-gradient-to-br">
        <div className="inset-shadow-shark-80 inset-ring-shark-80/50 text-shark-40 grid aspect-video w-7xl grid-rows-[1fr_1fr_1fr] rounded-lg bg-black/25 shadow-xl/50 inset-shadow-2xs inset-ring-2 backdrop-blur">
          <div></div>
          <div className="flex flex-col items-center justify-center gap-2">
            <div className="flex items-center justify-center gap-1 font-sans text-7xl font-extralight tabular-nums">
              <span>{hours}</span>
              <span className="opacity-90">:</span>
              <span>{minutes}</span>
            </div>
            <div className="font-caps flex items-center justify-center gap-1 text-2xl tabular-nums">
              {dayName}, {monthName} {day}, {year}
            </div>
          </div>
          <div></div>
        </div>
      </div>
    </Canvas>
  )
}
