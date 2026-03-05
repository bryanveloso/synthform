import { useEffect, useState, useCallback } from 'react'

import { useRealtimeStore } from '@/store/realtime'
import { serverConnection } from './use-server'
import type { OBSState } from '@/types/obs'

export function useOBS() {
  const storeObs = useRealtimeStore((s) => s.obs)
  const isConnected = useRealtimeStore((s) => s.isConnected)

  const [state, setState] = useState<OBSState>({
    connected: false,
    currentScene: null,
    currentProgramScene: null,
    streaming: false,
    recording: false,
    virtualCam: false,
    scenes: [],
    sceneItems: [],
    streamStatus: null,
  })

  const [isDropping, setIsDropping] = useState(false)
  const [dropRate, setDropRate] = useState(0)

  // Sync store OBS data to local state
  // The store handles obs:sync and obs:update; granular events
  // (scene:changed, stream:started, etc.) will be added to the
  // store when OBS integration is fully implemented.
  useEffect(() => {
    if (storeObs.scene || storeObs.stream) {
      setState(prev => ({
        ...prev,
        connected: true,
        currentScene: storeObs.scene?.current_scene ?? prev.currentScene,
        currentProgramScene: storeObs.scene?.current_scene ?? prev.currentProgramScene,
        streaming: storeObs.stream?.streaming ?? prev.streaming,
        recording: storeObs.stream?.recording ?? prev.recording,
      }))
    }
  }, [storeObs])

  // Reset performance metrics when disconnected
  useEffect(() => {
    if (!isConnected) {
      setIsDropping(false)
      setDropRate(0)
    }
  }, [isConnected])

  const refreshBrowserSource = useCallback((sourceName: string) => {
    serverConnection.send('obs:browser:refresh', { sourceName })
  }, [])

  const setScene = useCallback((sceneName: string) => {
    serverConnection.send('obs:scene:set', { sceneName })
  }, [])

  const startStreaming = useCallback(() => {
    serverConnection.send('obs:stream:start', {})
  }, [])

  const stopStreaming = useCallback(() => {
    serverConnection.send('obs:stream:stop', {})
  }, [])

  const startRecording = useCallback(() => {
    serverConnection.send('obs:record:start', {})
  }, [])

  const stopRecording = useCallback(() => {
    serverConnection.send('obs:record:stop', {})
  }, [])

  return {
    ...state,
    isConnected,
    isDropping,
    dropRate,
    refreshBrowserSource,
    setScene,
    startStreaming,
    stopStreaming,
    startRecording,
    stopRecording,
  }
}

