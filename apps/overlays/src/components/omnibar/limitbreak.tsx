import { useState, useEffect, useRef, type FC, type PropsWithChildren } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['limitbreak:sync', 'limitbreak:update', 'limitbreak:executed'] as const

interface LimitBreakData {
  count: number
  bar1: number
  bar2: number
  bar3: number
  isMaxed: boolean
}

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
  const { data, isConnected } = useServer(MESSAGE_TYPES)
  const [limitBreakData, setLimitBreakData] = useState<LimitBreakData | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const executionAudioRef = useRef<HTMLAudioElement>(null)
  const previousIsMaxedRef = useRef<boolean>(false)

  const limitBreakSync = data['limitbreak:sync']
  const limitBreakUpdate = data['limitbreak:update']
  const limitBreakExecuted = data['limitbreak:executed']

  useEffect(() => {
    if (limitBreakSync) {
      setLimitBreakData(limitBreakSync)
      previousIsMaxedRef.current = limitBreakSync.isMaxed
    }
  }, [limitBreakSync])

  useEffect(() => {
    if (limitBreakUpdate) {
      const previousIsMaxed = previousIsMaxedRef.current
      const newIsMaxed = limitBreakUpdate.isMaxed

      setLimitBreakData(limitBreakUpdate)

      // Play sound when transitioning from not maxed to maxed
      if (!previousIsMaxed && newIsMaxed && audioRef.current) {
        audioRef.current.volume = 0.2
        audioRef.current.play().catch((error) => {
          console.warn('Could not play limit break sound:', error)
        })
      }

      previousIsMaxedRef.current = newIsMaxed
    }
  }, [limitBreakUpdate])

  // Handle limit break execution
  useEffect(() => {
    if (limitBreakExecuted && executionAudioRef.current) {
      executionAudioRef.current.volume = 0.3 // Set appropriate volume
      executionAudioRef.current.play().catch((error) => {
        console.warn('Could not play limit break execution sound:', error)
      })
    }
  }, [limitBreakExecuted])

  if (!limitBreakData) {
    return (
      <div>
        <div>Limit Break: {isConnected ? 'Waiting for data...' : 'Disconnected'}</div>
        <div style={{ fontSize: '12px', color: '#666' }}>
          Connected: {isConnected ? 'Yes' : 'No'} | Sync: {data['limitbreak:sync'] ? 'Yes' : 'No'} | Update:{' '}
          {data['limitbreak:update'] ? 'Yes' : 'No'}
        </div>
      </div>
    )
  }

  const { count, bar1, bar2, bar3 } = limitBreakData

  return (
    <div>
      <div className="flex items-center justify-center gap-2">
        <Bar>
          <Progress bar={bar1} isFilled={bar1 >= 1} />
        </Bar>
        <Bar>
          <Progress bar={bar2} isFilled={bar2 >= 1} />
        </Bar>
        <Bar>
          <Progress bar={bar3} isFilled={bar3 >= 1} />
        </Bar>
        <div className="font-sans font-bold text-[#0096ff]">{count}</div>
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
