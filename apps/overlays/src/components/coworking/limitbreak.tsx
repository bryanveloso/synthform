import { useEffect, useRef, useCallback, type FC, type PropsWithChildren } from 'react'
import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'

import { useLimitbreak } from '@/hooks/use-limitbreak'
import { cn } from '@/lib/utils'
import { animateLimitBreakMaxed, animateLimitBreakExecute } from '@/lib/animations'

const Bar: FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="outline-shark-520 border-shark-920 bg-shark-840 relative h-3 w-20 overflow-hidden rounded-xs border-2 outline-2">
      {children}
    </div>
  )
}

const Progress: FC<{ bar: number; isFilled: boolean }> = ({ bar, isFilled }) => {
  return (
    <div
      className={cn(
        'h-full bg-gradient-to-r',
        isFilled ? 'from-[#ff8416] via-[#ffff08] to-[#ff8416]' : 'from-[#0096ff] via-[#4adfff] to-[#ffffff]',
        'ease transition-all duration-300',
      )}
      style={{ width: `${bar * 100}%` }}
    />
  )
}

export const LimitBreak = () => {
  const { data, count, progress, filledBars, hasJustMaxed, hasJustExecuted, isConnected, isReady } = useLimitbreak()

  const audioRef = useRef<HTMLAudioElement>(null)
  const executionAudioRef = useRef<HTMLAudioElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const barsRef = useRef<HTMLDivElement[]>([])
  const hasAnimatedEntrance = useRef(false)

  // Play sound when limit break becomes maxed
  useEffect(() => {
    if (hasJustMaxed && audioRef.current) {
      audioRef.current.volume = 0.075
      audioRef.current.play().catch((error) => {
        console.warn('Could not play limit break sound:', error)
      })
    }
  }, [hasJustMaxed])

  // Play sound when limit break is executed
  useEffect(() => {
    if (hasJustExecuted && executionAudioRef.current) {
      executionAudioRef.current.volume = 0.075
      executionAudioRef.current
        .play()
        .then(() => {
          console.log('Limit break execution sound played')
        })
        .catch((error) => {
          console.error('Could not play limit break execution sound:', error)
        })
    }
  }, [hasJustExecuted])

  // Animate maxed state
  useGSAP(() => {
    if (isReady && barsRef.current.length) {
      barsRef.current.forEach(bar => {
        if (bar) animateLimitBreakMaxed(bar)
      })
    }
  }, [isReady])

  // Animate execution
  useGSAP(() => {
    if (hasJustExecuted && containerRef.current) {
      animateLimitBreakExecute(containerRef.current)
    }
  }, [hasJustExecuted])

  // Simple entrance animation when data loads
  useGSAP(() => {
    if (data && containerRef.current && !hasAnimatedEntrance.current) {
      gsap.fromTo(containerRef.current,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out' }
      )
      hasAnimatedEntrance.current = true
    }
  }, [data])

  // Create reusable ref setter
  const setBarRef = useCallback((index: number) => (el: HTMLDivElement | null) => {
    if (el) barsRef.current[index] = el
  }, [])

  if (!data) {
    return (
      <div data-limitbreak className="pr-[26px]">
        {/* <div>Limit Break: {isConnected ? 'Waiting for data...' : 'Disconnected'}</div> */}
      </div>
    )
  }

  const { bar1, bar2, bar3 } = data

  return (
    <div ref={containerRef} className="pr-[26px]" data-limitbreak>
      <div className="flex items-center justify-center gap-3">
        <div className="font-caps text-shark-120 flex items-center gap-1 text-2xl">{count}</div>
        <div ref={setBarRef(0)}>
          <Bar>
            <Progress bar={bar1} isFilled={filledBars.bar1} />
          </Bar>
        </div>
        <div ref={setBarRef(1)}>
          <Bar>
            <Progress bar={bar2} isFilled={filledBars.bar2} />
          </Bar>
        </div>
        <div ref={setBarRef(2)}>
          <Bar>
            <Progress bar={bar3} isFilled={filledBars.bar3} />
          </Bar>
        </div>
      </div>
      <audio ref={audioRef} preload="auto" className="hidden">
        <source src="/sounds/limit-break.mp3" type="audio/mpeg" />
      </audio>
      <audio ref={executionAudioRef} preload="auto" className="hidden">
        <source src="/sounds/limit-break-executed.mp3" type="audio/mpeg" />
      </audio>
    </div>
  )
}
