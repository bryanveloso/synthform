// Base music data shared by all sources
export interface BaseMusicTrack {
  id: string
  title: string
  artist: string
  album?: string
  artwork?: string
  duration?: number  // in seconds
  elapsed?: number   // in seconds
  timestamp: string
}

// Rainwave-specific song data
export interface RainwaveSong extends BaseMusicTrack {
  game?: string      // For Rainwave, album is the game
  station?: string   // Station name
  url?: string       // OCRemix URL
  requested_by?: string  // Username who requested
  requested_by_id?: string
  event_id?: string
  event_type?: string  // OneUp, Election, etc.
  votes?: number     // For elections
  is_request?: boolean
  is_crusader?: boolean  // True if requester is a community member
}

// Rainwave election (voting) data
export interface RainwaveElection {
  event_id: string
  event_type: 'Election'
  voting_allowed: boolean
  songs: RainwaveSong[]
}

// Complete Rainwave data with queue and history
export interface RainwaveData extends RainwaveSong {
  source: 'rainwave'
  upcoming?: Array<RainwaveSong | RainwaveElection>  // Next tracks/elections
  history?: RainwaveSong[]   // Previous tracks
}

// Apple Music data
export interface AppleMusicData extends BaseMusicTrack {
  source: 'apple'
  playing?: boolean
  position?: number  // Apple uses position instead of elapsed
}

// Union type for all music sources
export type MusicData = RainwaveData | AppleMusicData

// Type guards
export function isRainwaveData(data: MusicData): data is RainwaveData {
  return data.source === 'rainwave'
}

export function isAppleMusicData(data: MusicData): data is AppleMusicData {
  return data.source === 'apple'
}

export function isRainwaveElection(data: any): data is RainwaveElection {
  return data.event_type === 'Election' && Array.isArray(data.songs)
}

// Music state for the hook
export interface MusicState {
  current: MusicData | null
  previous: MusicData | null
  isPlaying: boolean
  source: 'rainwave' | 'apple' | null
  lastUpdate: string | null
  // Rainwave-specific queue data
  upcoming?: Array<RainwaveSong | RainwaveElection>
  history?: RainwaveSong[]
}