import { useState, useEffect, useRef, type FC, type PropsWithChildren } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['limitbreak:sync', 'limitbreak:update'] as const

interface LimitBreakData {
  count: number
  bar1: number
  bar2: number
  bar3: number
  isMaxed: boolean
}

const Bar: FC<PropsWithChildren> = ({ children }) => {
  return <div className="relative h-3 w-12 bg-[#1E3246]">{children}</div>
}

const Progress: FC<{ bar: number; isMaxed: boolean }> = ({ bar, isMaxed }) => {
  return (
    <div
      style={{
        width: `${bar * 100}%`,
        height: '100%',
        backgroundColor: isMaxed ? '#ff6b6b' : '#4ecdc4',
        transition: 'width 0.3s ease',
      }}
    />
  )
}

export const LimitBreak = () => {
  const { data, isConnected } = useServer(MESSAGE_TYPES)
  const [limitBreakData, setLimitBreakData] = useState<LimitBreakData | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const previousIsMaxedRef = useRef<boolean>(false)

  const limitBreakSync = data['limitbreak:sync']
  const limitBreakUpdate = data['limitbreak:update']

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

  const { count, bar1, bar2, bar3, isMaxed } = limitBreakData

  return (
    <div>
      <audio ref={audioRef} preload="auto" style={{ display: 'none' }}>
        <source src="/sounds/limit-break.mp3" type="audio/mpeg" />
      </audio>
      <div>
        {/* <div>Limit Break ({count}/100)</div> */}
        <div style={{ display: 'flex', gap: '4px' }}>
          <Bar>
            <Progress bar={bar1} isMaxed={isMaxed} />
          </Bar>
          <Bar>
            <Progress bar={bar2} isMaxed={isMaxed} />
          </Bar>
          <Bar>
            <Progress bar={bar3} isMaxed={isMaxed} />
          </Bar>
        </div>
        {/* {isMaxed && <div style={{ color: '#ff6b6b', fontWeight: 'bold', marginTop: '4px' }}>LIMIT BREAK READY!</div>} */}
      </div>
    </div>
  )
}
