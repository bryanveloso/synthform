import { createFileRoute } from '@tanstack/react-router'

import { Canvas } from '@/components/ui/canvas'
import { Circle, Frame } from '@/components/ui/window'
import { LimitBreak } from '@/components/coworking/limitbreak'
import { Timeline } from '@/components/coworking/timeline'

export const Route = createFileRoute('/coworking')({
  component: RouteComponent,
})

function RouteComponent() {
  return (
    <Canvas>
      <div className="grid grid-rows-[auto_48px]">
        {/* Main Content */}
        <div className="grid grid-cols-[1fr_492px_auto] gap-3 p-6">
          <div className="flex flex-col gap-3">
            {/* !work */}
            <Frame toolbar>
              <div className="flex items-center gap-2 py-1.5 pr-11 pl-1">
                <Circle />
                <Circle />
                <Circle />
                <div className="font-caps flex-1 text-center font-bold text-white">!coworking</div>
              </div>
              <div className="bg-shark-960 h-[936px] w-[762px]"></div>
            </Frame>

            {/* <div className="rounded-lg p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10">
              <div className="transparent aspect-[39/22] h-[264px]"></div>
            </div> */}
          </div>

          <div className="flex flex-col gap-3 self-end">
            {/* !status */}
            <div className="relative flex rounded-lg bg-gradient-to-b shadow-xl/50">
              <div className="absolute top-0 left-0 h-full w-full rounded-lg inset-ring-2 inset-ring-white/10"></div>

              <div className="from-shark-840 to-shark-880 flex items-center justify-center rounded-l-lg bg-gradient-to-b pr-4 pl-4.5">
                <div className="outline-shark-920 from-lime to-lime/50 size-3.5 rounded-full bg-radial-[at_50%_25%] outline-4"></div>
              </div>
              <div className="from-shark-880 to-shark-920 text-shark-240 flex-1 rounded-r-lg bg-gradient-to-b p-3 font-sans text-shadow-sm/50">
                Bryan is currently <span className="text-lime font-bold">online</span>.
              </div>

              {/* <div className="from-shark-840 to-shark-880 flex items-center justify-center rounded-l-lg bg-gradient-to-b pr-4 pl-4.5">
                <div className="outline-shark-920 from-marigold to-marigold/50 size-3.5 rounded-full bg-radial-[at_50%_25%] outline-4"></div>
              </div>
              <div className="from-shark-880 to-shark-920 text-shark-240 flex-1 rounded-r-lg bg-gradient-to-b p-3 font-sans text-shadow-sm/50">
                Bryan is currently <span className="text-marigold font-bold">away</span>.
              </div> */}
            </div>

            {/* !hire */}
            <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10">
              <div className="bg-shark-960 aspect-[39/22] h-[264px]"></div>
            </div>
          </div>

          {/* !ffbot */}
          <Frame toolbar>
            <div className="flex items-center gap-2 py-1.5 pr-11 pl-1">
              <Circle />
              <Circle />
              <Circle />
              <div className="font-caps flex-1 text-center font-bold text-white">!ffbot</div>
            </div>
            <div className="bg-shark-960 aspect-[7/12] h-[936px]"></div>
          </Frame>
        </div>

        {/* Bottom Bar */}
        <div className="bg-shark-960 inset-shadow relative flex min-w-0 items-center justify-between">
          <Timeline />
          <LimitBreak />
          <div className="absolute top-0 h-1 w-full bg-[#040506]"></div>
          <div className="from-marigold to-lime absolute bottom-0 h-[1px] w-full bg-gradient-to-l"></div>
        </div>
      </div>
    </Canvas>
  )
}
