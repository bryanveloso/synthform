import { useEffect, useRef, type FC, type PropsWithChildren } from 'react'

import { useLimitbreak } from '@/hooks/use-limitbreak'
import { cn } from '@/lib/utils'

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
  const { data, count, progress, filledBars, hasJustMaxed, hasJustExecuted, isConnected } = useLimitbreak()

  const audioRef = useRef<HTMLAudioElement>(null)
  const executionAudioRef = useRef<HTMLAudioElement>(null)

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

  if (!data) {
    return (
      <div>
        {/* <div>Limit Break: {isConnected ? 'Waiting for data...' : 'Disconnected'}</div> */}
      </div>
    )
  }

  const { bar1, bar2, bar3 } = data

  return (
    <div className="pr-[26px]">
      <div className="flex items-center justify-center gap-3">
        <div className="font-caps text-shark-120 flex items-center gap-1 text-2xl">{count}</div>
        <Bar>
          <Progress bar={bar1} isFilled={filledBars.bar1} />
        </Bar>
        <Bar>
          <Progress bar={bar2} isFilled={filledBars.bar2} />
        </Bar>
        <Bar>
          <Progress bar={bar3} isFilled={filledBars.bar3} />
        </Bar>
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
