import { useRef } from 'react'

import { Alert } from '@/components/shared/alert'
import { Campaign } from '@/components/shared/campaign'
import { Timeline } from '@/components/shared/timeline'
import { Canvas } from '@/components/ui/canvas'
import { useAlertQueue } from '@/hooks/use-alerts'
import { useMicStatus } from '@/hooks/use-rme'
import { cn } from '@/lib/utils'

export const Omnibar = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const { currentAlert, onAlertComplete, soundEnabled } = useAlertQueue({ soundEnabled: true })
  const { isMuted, isConnected } = useMicStatus()

  return (
    <Canvas>
      {/* Invisible alert sound handler */}
      <Alert currentAlert={currentAlert} onComplete={onAlertComplete} soundEnabled={soundEnabled} />

      <div ref={containerRef} className="h-canvas grid grid-rows-[1fr_64px]">
        <div className="h-full"></div>
        <div className="relative flex items-center">
          {/* Base layer: Campaign */}
          <div className="relative z-10 flex w-full items-center">
            <Campaign />

            <div className="text-shark-240 bg-shark-960 flex h-16 items-center px-6 font-sans text-lg text-shadow-sm/50">
              {isConnected && (
                <div
                  className={cn(
                    { 'opacity-100': isMuted, 'opacity-0': !isMuted },
                    'font-caps ring-shark-960 rounded-md bg-gradient-to-b from-rose-500 to-rose-700 px-2 ring-4 inset-ring-1 inset-ring-rose-400 transition-opacity duration-300 ease-in-out text-shadow-none',
                  )}>
                  MUTED
                </div>
              )}
            </div>
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
