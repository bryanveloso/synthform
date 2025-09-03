import { useState, useEffect, useRef } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['limitbreak:sync', 'limitbreak:update'] as const

interface LimitBreakData {
  count: number
  bar1: number
  bar2: number
  bar3: number
  isMaxed: boolean
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
        audioRef.current.play().catch(error => {
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
          Connected: {isConnected ? 'Yes' : 'No'} | 
          Sync: {data['limitbreak:sync'] ? 'Yes' : 'No'} | 
          Update: {data['limitbreak:update'] ? 'Yes' : 'No'}
        </div>
      </div>
    )
  }

  const { count, bar1, bar2, bar3, isMaxed } = limitBreakData

  return (
    <div>
      <audio
        ref={audioRef}
        preload="auto"
        style={{ display: 'none' }}
      >
        <source src="/sounds/limit-break.mp3" type="audio/mpeg" />
        <source src="/sounds/limit-break.ogg" type="audio/ogg" />
      </audio>
      <div>
        <div>Limit Break ({count}/100)</div>
        <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
          <div
            style={{
              width: '40px',
              height: '8px',
              backgroundColor: '#333',
              position: 'relative',
              border: '1px solid #666'
            }}
          >
            <div
              style={{
                width: `${bar1 * 100}%`,
                height: '100%',
                backgroundColor: isMaxed ? '#ff6b6b' : '#4ecdc4',
                transition: 'width 0.3s ease'
              }}
            />
          </div>
          <div
            style={{
              width: '40px',
              height: '8px',
              backgroundColor: '#333',
              position: 'relative',
              border: '1px solid #666'
            }}
          >
            <div
              style={{
                width: `${bar2 * 100}%`,
                height: '100%',
                backgroundColor: isMaxed ? '#ff6b6b' : '#4ecdc4',
                transition: 'width 0.3s ease'
              }}
            />
          </div>
          <div
            style={{
              width: '40px',
              height: '8px',
              backgroundColor: '#333',
              position: 'relative',
              border: '1px solid #666'
            }}
          >
            <div
              style={{
                width: `${bar3 * 100}%`,
                height: '100%',
                backgroundColor: isMaxed ? '#ff6b6b' : '#4ecdc4',
                transition: 'width 0.3s ease'
              }}
            />
          </div>
        </div>
        {isMaxed && (
          <div style={{ color: '#ff6b6b', fontWeight: 'bold', marginTop: '4px' }}>
            LIMIT BREAK READY!
          </div>
        )}
      </div>
    </div>
  )
}