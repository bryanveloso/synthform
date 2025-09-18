// Import types from obs-websocket-js for reference
import type {
  OBSResponseTypes,
  OBSEventTypes,
} from 'obs-websocket-js'

// Re-export useful types
export type GetSceneListResponse = OBSResponseTypes['GetSceneList']
export type GetSceneItemListResponse = OBSResponseTypes['GetSceneItemList']
export type GetStreamStatusResponse = OBSResponseTypes['GetStreamStatus']
export type CurrentProgramSceneChangedEvent = OBSEventTypes['CurrentProgramSceneChanged']
export type StreamStateChangedEvent = OBSEventTypes['StreamStateChanged']
export type RecordStateChangedEvent = OBSEventTypes['RecordStateChanged']
export type VirtualcamStateChangedEvent = OBSEventTypes['VirtualcamStateChanged']

// Our custom OBS state interface
export interface OBSState {
  connected: boolean
  currentScene: string | null
  currentProgramScene: string | null
  streaming: boolean
  recording: boolean
  virtualCam: boolean
  scenes: GetSceneListResponse['scenes']
  sceneItems: GetSceneItemListResponse['sceneItems']
  streamStatus: GetStreamStatusResponse | null
}

// OBS WebSocket message types for our server
export interface OBSStatusMessage {
  connected: boolean
  streaming?: boolean
  recording?: boolean
  virtualCam?: boolean
  currentScene?: string
  currentProgramScene?: string
}

export interface OBSSceneChangedMessage {
  sceneName: string
  sceneUuid?: string
}

export interface OBSScenesListMessage {
  currentProgramSceneName: string
  currentProgramSceneUuid?: string
  currentPreviewSceneName?: string
  currentPreviewSceneUuid?: string
  scenes: GetSceneListResponse['scenes']
}

export interface OBSSceneItemsMessage {
  sceneName: string
  sceneUuid?: string
  sceneItems: GetSceneItemListResponse['sceneItems']
}

export interface OBSStreamStatusMessage extends GetStreamStatusResponse {}

// Command messages we send to the server
export interface OBSCommand {
  command: string
  data?: any
}

export interface RefreshBrowserSourceCommand {
  sourceName: string
}

export interface SetSceneCommand {
  sceneName: string
}