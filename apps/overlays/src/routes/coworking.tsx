import { createFileRoute } from '@tanstack/react-router'

import { Canvas } from '@/components/ui/canvas'
import { Circle, Frame } from '@/components/ui/window'

export const Route = createFileRoute('/coworking')({
  component: RouteComponent,
})

function RouteComponent() {
  return (
    <Canvas>
      <div className="grid grid-rows-[auto_48px]">
        {/* Main Content */}
        <div className="grid grid-cols-[1fr_492px_auto] gap-3 p-6">
          {/* !work */}
          <Frame toolbar>
            <div className="flex items-center gap-2 py-2 pr-11 pl-1">
              <Circle />
              <Circle />
              <Circle />
              <div className="font-caps flex-1 text-center font-bold text-white">!coworking</div>
            </div>
            <div className="bg-shark-960 h-[936px] w-[762px]"></div>
          </Frame>

          {/* !hire */}
          <div className="from-shark-880 to-shark-920 self-end rounded-lg bg-gradient-to-b p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10">
            <div className="bg-shark-960 aspect-[39/22] h-[264px]"></div>
          </div>

          {/* !ffbot */}
          <Frame toolbar>
            <div className="flex items-center gap-2 py-2 pr-11 pl-1">
              <Circle />
              <Circle />
              <Circle />
              <div className="font-caps flex-1 text-center font-bold text-white">!ffbot</div>
            </div>
            <div className="bg-shark-960 aspect-[7/12] h-[936px]"></div>
          </Frame>
        </div>

        {/* Bottom Bar */}
        <div className=""></div>
      </div>
    </Canvas>
  )
}
