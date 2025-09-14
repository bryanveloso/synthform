import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
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
  
  // Track interpolated elapsed time
  const [interpolatedElapsed, setInterpolatedElapsed] = useState(0)
  const animationFrameRef = useRef<number>()
  
  // Memoize the message types array to prevent infinite loops
  const messageTypes = useMemo(() => ['music:sync', 'music:update'] as const, [])
  const { data, isConnected } = useServer(messageTypes)

  const updateMusicState = useCallback((data: any) => {
    setMusicState(prev => {
      // Check if this is a "tuned out" signal
      if (data.tuned_in === false) {
        return {
          current: null,
          previous: prev.current,
          isPlaying: false,
          source: data.source || prev.source,
          lastUpdate: data.timestamp || new Date().toISOString(),
        }
      }
      
      // If data has an id, it's the track data
      if (data.id) {
        // Normalize Apple Music data structure
        const normalizedData = data.source === 'apple' ? {
          ...data,
          elapsed: data.position || data.elapsed || 0,
          isPlaying: data.playing !== undefined ? data.playing : true,
        } : data
        
        // New track
        if (data.id !== prev.current?.id) {
          // Reset interpolation for new track
          setInterpolatedElapsed(normalizedData.elapsed)
          
          return {
            current: normalizedData as MusicTrack,
            previous: prev.current,
            isPlaying: normalizedData.isPlaying,
            source: data.source || 'rainwave',
            lastUpdate: data.timestamp || new Date().toISOString(),
          }
        }
        // Same track, update elapsed time only if it changed
        const currentElapsed = normalizedData.elapsed
        if (prev.current && currentElapsed !== prev.current.elapsed) {
          // Reset interpolation starting point when we get a new position
          setInterpolatedElapsed(currentElapsed)
          
          return {
            ...prev,
            current: { ...prev.current, elapsed: currentElapsed },
            isPlaying: normalizedData.isPlaying,
          }
        }
        // No changes
        return prev
      }
      
      // If data has a current property, it's wrapped (future format)
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

  // Smooth interpolation of elapsed time
  useEffect(() => {
    if (!musicState.isPlaying || !musicState.current?.duration) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      return
    }

    const startTime = Date.now()
    const startElapsed = musicState.current?.elapsed || 0

    const animate = () => {
      const now = Date.now()
      const deltaTime = (now - startTime) / 1000 // Convert to seconds
      const newElapsed = Math.min(startElapsed + deltaTime, musicState.current?.duration || 0)
      
      setInterpolatedElapsed(newElapsed)
      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [musicState.isPlaying, musicState.current?.elapsed, musicState.current?.duration])

  // Computed values - use interpolated elapsed for smooth progress
  const displayElapsed = musicState.isPlaying ? interpolatedElapsed : (musicState.current?.elapsed || 0)
  const progress = displayElapsed && musicState.current?.duration
    ? (displayElapsed / musicState.current.duration) * 100
    : 0

  const formattedElapsed = formatTime(displayElapsed)
  const formattedDuration = formatTime(musicState.current?.duration || 0)

  return {
    ...musicState,
    current: musicState.current ? {
      ...musicState.current,
      elapsed: displayElapsed  // Override with interpolated value
    } : null,
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