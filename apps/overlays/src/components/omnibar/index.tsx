import { useRef } from 'react'

import { Canvas } from '@/components/ui/canvas'

import { Timeline } from './timeline'

export const Omnibar = () => {
  const containerRef = useRef<HTMLDivElement>(null)

  return (
    <Canvas>
      <div ref={containerRef} className="grid grid-rows-[auto_64px]">
        <div className="h-[calc(100vh-64px)]"></div>
        <div className="relative">
          <div className="inset-shadow-shark-960/100 absolute z-10 h-16 w-full inset-shadow-sm" />
          <Timeline />
        </div>
      </div>
    </Canvas>
  )
}
