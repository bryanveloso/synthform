import { useEffect, useState, useCallback, useMemo } from 'react'
import { useServer } from './use-server'

export interface MusicTrack {
  id: string
  title: string
  artist: string
  album?: string
  game?: string  // For Rainwave
  artwork?: string
  duration?: number  // in seconds
  elapsed?: number   // in seconds
  source: 'rainwave' | 'apple' | 'spotify'
  station?: string   // For Rainwave
  url?: string       // For Rainwave
  timestamp: string
}

export interface MusicState {
  current: MusicTrack | null
  previous: MusicTrack | null
  isPlaying: boolean
  source: string | null
  lastUpdate: string | null
}

export function useMusic() {
  const [musicState, setMusicState] = useState<MusicState>({
    current: null,
    previous: null,
    isPlaying: false,
    source: null,
    lastUpdate: null,
  })
  
  // Memoize the message types array to prevent infinite loops
  const messageTypes = useMemo(() => ['music:sync', 'music:update'] as const, [])
  const { data, isConnected } = useServer(messageTypes)

  const updateMusicState = useCallback((data: any) => {
    setMusicState(prev => {
      // If data has an id, it's the track data directly from Rainwave
      if (data.id) {
        // New track
        if (data.id !== prev.current?.id) {
          return {
            current: data as MusicTrack,
            previous: prev.current,
            isPlaying: true,  // Rainwave is always playing
            source: data.source || 'rainwave',
            lastUpdate: data.timestamp || new Date().toISOString(),
          }
        }
        // Same track, update elapsed time only if it changed
        if (prev.current && data.elapsed !== prev.current.elapsed) {
          return {
            ...prev,
            current: { ...prev.current, elapsed: data.elapsed },
          }
        }
        // No changes
        return prev
      }
      
      // If data has a current property, it's wrapped (future Apple Music format)
      if (data.current) {
        if (data.current.id !== prev.current?.id) {
          return {
            current: data.current,
            previous: prev.current,
            isPlaying: data.isPlaying ?? true,
            source: data.source || prev.source,
            lastUpdate: data.timestamp || new Date().toISOString(),
          }
        }
        // Same track, don't update state
        return prev
      }
      
      // Unknown format, return previous state
      return prev
    })
  }, [])

  // Extract data values to avoid complex dependency warnings
  const musicSyncData = data['music:sync']
  const musicUpdateData = data['music:update']

  useEffect(() => {
    if (musicSyncData) {
      updateMusicState(musicSyncData)
    }
  }, [musicSyncData, updateMusicState])

  useEffect(() => {
    if (musicUpdateData) {
      updateMusicState(musicUpdateData)
    }
  }, [musicUpdateData, updateMusicState])

  // Computed values
  const progress = musicState.current?.elapsed && musicState.current?.duration
    ? (musicState.current.elapsed / musicState.current.duration) * 100
    : 0

  const formattedElapsed = formatTime(musicState.current?.elapsed || 0)
  const formattedDuration = formatTime(musicState.current?.duration || 0)

  return {
    ...musicState,
    isConnected,
    progress,
    formattedElapsed,
    formattedDuration,
  }
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}