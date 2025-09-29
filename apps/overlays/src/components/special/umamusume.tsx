import { useGSAP } from '@gsap/react'
import { useRef } from 'react'

import { Alert } from '@/components/shared/alert'
import { Timeline } from '@/components/shared/timeline'
import { Status } from '@/components/coworking/status'
import { Campaign } from '@/components/shared/campaign'
import { Canvas } from '@/components/ui/canvas'
import { Circle, Frame } from '@/components/ui/window'
import { animateOverlayEntrance } from '@/lib/animations'
import { useAlertQueue } from '@/hooks/use-alerts'

export const Umamusume = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const { currentAlert, onAlertComplete, soundEnabled } = useAlertQueue({ soundEnabled: true })

  // Animate entire overlay on mount
  useGSAP(() => {
    if (containerRef.current) {
      animateOverlayEntrance(containerRef.current)
    }
  }, [])

  return (
    <Canvas>
      {/* Invisible alert sound handler */}
      <Alert currentAlert={currentAlert} onComplete={onAlertComplete} soundEnabled={soundEnabled} />

      <div ref={containerRef} className="grid grid-rows-[auto_64px]">
        {/* Main Content */}
        <div className="grid grid-cols-[714px_auto_561px] gap-3 p-6">
          <div className="flex flex-col gap-3">
            {/* !umamusume */}
            <Frame toolbar>
              <div className="flex items-center gap-2 py-1.5 pr-11 pl-1">
                <Circle />
                <Circle />
                <Circle />
                <div className="font-caps flex-1 text-center font-bold text-white">Umamusume: Pretty Derby</div>
              </div>
              <div className="bg-shark-960 aspect-[3/4] h-[920px]"></div>
            </Frame>
          </div>

          <div className="flex flex-col gap-3 self-end">
            {/* !status */}
            <Status />

            {/* !hire */}
            <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10">
              <div className="bg-shark-960 aspect-[39/22] w-[549px]"></div>
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
            <div className="bg-shark-960 aspect-[7/12] h-[920px]"></div>
          </Frame>
        </div>

        {/* Bottom Bar - Layered chyron system */}
        <div className="w-canvas relative flex items-center">
          {/* Base layer: Campaign (z-10) */}
          <div className="w-canvas bg-shark-960 relative z-10 flex items-center justify-between">
            <Campaign />
          </div>

          {/* Timeline layer: Overlays on top (z-20) */}
          <div className="absolute inset-0 z-20 flex items-center">
            <Timeline />
          </div>

          {/* Decorative borders */}
          <div className="absolute top-0 z-50 h-1 w-full bg-[#040506]"></div>
          <div className="from-marigold to-lime absolute bottom-0 z-50 h-[1px] w-full bg-gradient-to-r"></div>
        </div>
      </div>
    </Canvas>
  )
}
