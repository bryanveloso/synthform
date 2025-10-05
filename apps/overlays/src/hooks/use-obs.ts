import { useEffect, useState, useCallback } from 'react'

import type { OBSState } from '@/types/obs'

import { useServer } from './use-server'

export function useOBS() {
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

  const { data, isConnected, send } = useServer([
    'obs:status',
    'obs:scene:changed',
    'obs:stream:started',
    'obs:stream:stopped',
    'obs:record:started',
    'obs:record:stopped',
    'obs:virtualcam:started',
    'obs:virtualcam:stopped',
    'obs:scenes:list',
    'obs:scene:items',
    'obs:stream:status',
    'obs:performance',
  ] as const)

  const statusData = data['obs:status']
  const sceneData = data['obs:scene:changed']
  const scenesListData = data['obs:scenes:list']
  const sceneItemsData = data['obs:scene:items']
  const streamStatusData = data['obs:stream:status']
  const performanceData = data['obs:performance']

  useEffect(() => {
    if (statusData) {
      setState(prev => ({
        ...prev,
        connected: statusData.connected ?? false,
        streaming: statusData.streaming ?? false,
        recording: statusData.recording ?? false,
        virtualCam: statusData.virtualCam ?? false,
        currentScene: statusData.currentScene ?? prev.currentScene,
        currentProgramScene: statusData.currentProgramScene ?? prev.currentProgramScene,
      }))
    }
  }, [statusData])

  useEffect(() => {
    if (sceneData) {
      setState(prev => ({
        ...prev,
        currentScene: sceneData.sceneName,
        currentProgramScene: sceneData.sceneName,
      }))
    }
  }, [sceneData])

  useEffect(() => {
    if (scenesListData) {
      setState(prev => ({
        ...prev,
        scenes: scenesListData.scenes ?? [],
        currentProgramScene: scenesListData.currentProgramSceneName ?? prev.currentProgramScene,
      }))
    }
  }, [scenesListData])

  useEffect(() => {
    if (sceneItemsData) {
      setState(prev => ({
        ...prev,
        sceneItems: sceneItemsData.sceneItems ?? [],
      }))
    }
  }, [sceneItemsData])

  useEffect(() => {
    if (streamStatusData) {
      setState(prev => ({
        ...prev,
        streamStatus: streamStatusData,
      }))
    }
  }, [streamStatusData])

  const streamStarted = data['obs:stream:started']
  const streamStopped = data['obs:stream:stopped']
  const recordStarted = data['obs:record:started']
  const recordStopped = data['obs:record:stopped']
  const virtualCamStarted = data['obs:virtualcam:started']
  const virtualCamStopped = data['obs:virtualcam:stopped']

  useEffect(() => {
    if (streamStarted) {
      setState(prev => ({ ...prev, streaming: true }))
    }
  }, [streamStarted])

  useEffect(() => {
    if (streamStopped) {
      setState(prev => ({ ...prev, streaming: false }))
    }
  }, [streamStopped])

  useEffect(() => {
    if (recordStarted) {
      setState(prev => ({ ...prev, recording: true }))
    }
  }, [recordStarted])

  useEffect(() => {
    if (recordStopped) {
      setState(prev => ({ ...prev, recording: false }))
    }
  }, [recordStopped])

  useEffect(() => {
    if (virtualCamStarted) {
      setState(prev => ({ ...prev, virtualCam: true }))
    }
  }, [virtualCamStarted])

  useEffect(() => {
    if (virtualCamStopped) {
      setState(prev => ({ ...prev, virtualCam: false }))
    }
  }, [virtualCamStopped])

  useEffect(() => {
    if (performanceData) {
      setIsDropping(performanceData.isWarning ?? false)
      setDropRate(performanceData.dropRate ?? 0)
    }
  }, [performanceData])

  useEffect(() => {
    if (!isConnected) {
      setIsDropping(false)
      setDropRate(0)
    }
  }, [isConnected])

  const refreshBrowserSource = useCallback((sourceName: string) => {
    send('obs:browser:refresh', { sourceName })
  }, [send])

  const setScene = useCallback((sceneName: string) => {
    send('obs:scene:set', { sceneName })
  }, [send])

  const startStreaming = useCallback(() => {
    send('obs:stream:start', {})
  }, [send])

  const stopStreaming = useCallback(() => {
    send('obs:stream:stop', {})
  }, [send])

  const startRecording = useCallback(() => {
    send('obs:record:start', {})
  }, [send])

  const stopRecording = useCallback(() => {
    send('obs:record:stop', {})
  }, [send])

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

