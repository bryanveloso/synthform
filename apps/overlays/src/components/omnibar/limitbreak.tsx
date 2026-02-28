import { useEffect, useRef, type FC, type PropsWithChildren } from 'react'

import { useLimitbreak } from '@/hooks/use-limitbreak'

const Bar: FC<PropsWithChildren> = ({ children }) => {
  return <div className="relative h-3 w-16 overflow-hidden rounded-xs bg-[#1E3246]">{children}</div>
}

const Progress: FC<{ bar: number; isFilled: boolean }> = ({ bar, isFilled }) => {
  return (
    <div
      style={{
        width: `${bar * 100}%`,
        height: '100%',
        backgroundColor: isFilled ? '#ffff08' : '#0096ff',
        transition: 'width 0.3s ease',
      }}
    />
  )
}

export const LimitBreak = () => {
  const { data, count, filledBars, hasJustMaxed, hasJustExecuted, isConnected } = useLimitbreak()
  
  const audioRef = useRef<HTMLAudioElement>(null)
  const executionAudioRef = useRef<HTMLAudioElement>(null)

  // Play sound when limit break becomes maxed
  useEffect(() => {
    if (hasJustMaxed && audioRef.current) {
      audioRef.current.volume = 0.1
      audioRef.current.play().catch((error) => {
        console.warn('Could not play limit break sound:', error)
      })
    }
  }, [hasJustMaxed])

  // Play sound when limit break is executed
  useEffect(() => {
    if (hasJustExecuted && executionAudioRef.current) {
      executionAudioRef.current.volume = 0.1
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
        <div>Limit Break: {isConnected ? 'Waiting for data...' : 'Disconnected'}</div>
      </div>
    )
  }

  const { bar1, bar2, bar3 } = data

  return (
    <div>
      <div className="flex items-center justify-center gap-2">
        <Bar>
          <Progress bar={bar1} isFilled={filledBars.bar1} />
        </Bar>
        <Bar>
          <Progress bar={bar2} isFilled={filledBars.bar2} />
        </Bar>
        <Bar>
          <Progress bar={bar3} isFilled={filledBars.bar3} />
        </Bar>
        <div className="font-sans font-bold text-[#0096ff]">{count}</div>
      </div>
      <audio ref={audioRef} preload="auto" className="hidden">
        <source src="/sounds/limit-break.ogg" type="audio/ogg" />
      </audio>
      <audio ref={executionAudioRef} preload="auto" className="hidden">
        <source src="/sounds/limit-break-executed.ogg" type="audio/ogg" />
      </audio>
    </div>
  )
}
