import { useRef } from 'react'

import { Alert } from '@/components/shared/alert'
import { Timeline } from '@/components/shared/timeline'
import { Campaign } from '@/components/shared/campaign'
import { Canvas } from '@/components/ui/canvas'
import { useAlertQueue } from '@/hooks/use-alerts'

export const Podcast = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const { currentAlert, onAlertComplete, soundEnabled } = useAlertQueue({ soundEnabled: false })

  return (
    <Canvas>
      {/* Invisible alert sound handler */}
      <Alert currentAlert={currentAlert} onComplete={onAlertComplete} soundEnabled={soundEnabled} />

      <div ref={containerRef} className="h-canvas grid grid-rows-[1fr_64px]">
        {/* Main content area - empty for podcast view */}
        <div className="flex items-center justify-center">
          {/* Could add visual elements here if needed */}
        </div>

        {/* Timeline row at bottom */}
        <div className="relative flex items-center">
          {/* Base layer: Campaign */}
          <div className="relative z-10 flex w-full items-center">
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
