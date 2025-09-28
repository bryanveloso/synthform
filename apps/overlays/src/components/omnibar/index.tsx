import { useRef } from 'react'

import { Alert } from '@/components/shared/alert'
import { Campaign } from '@/components/shared/campaign'
import { Timeline } from '@/components/shared/timeline'
import { Canvas } from '@/components/ui/canvas'
import { useAlertQueue } from '@/hooks/use-alerts'

export const Omnibar = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const { currentAlert, onAlertComplete, soundEnabled } = useAlertQueue({ soundEnabled: true })

  return (
    <Canvas>
      {/* Invisible alert sound handler */}
      <Alert currentAlert={currentAlert} onComplete={onAlertComplete} soundEnabled={soundEnabled} />

      <div ref={containerRef} className="h-canvas grid grid-rows-[1fr_64px]">
        <div className="h-full"></div>
        <div className="relative flex items-center">
          {/* Base layer: Campaign */}
          <div className="relative z-10 flex items-center w-full">
            <Campaign />
          </div>

          {/* Timeline layer: Overlays on top */}
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
