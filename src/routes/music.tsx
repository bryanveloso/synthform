import { createFileRoute } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { useMusic } from '@/hooks/use-music'
import { isRainwaveData, isRainwaveElection } from '@/types/music'
import type { MusicData, RainwaveSong, RainwaveElection } from '@/types/music'
import { cn } from '@/lib/utils'

interface MusicViewProps {
  currentTrack: MusicData | null
  progress: number
  formatTime: (seconds: number) => string
}

interface RainwaveViewProps extends MusicViewProps {
  upcoming?: Array<RainwaveSong | RainwaveElection>
  history?: RainwaveSong[]
}

interface AppleMusicViewProps extends MusicViewProps {
  previousTrack: MusicData | null
  isPlaying: boolean
}

export const Route = createFileRoute('/music')({
  component: MusicComponent,
})

function MusicComponent() {
  const { current: currentTrack, previous: previousTrack, isPlaying, source, isConnected, upcoming, history } = useMusic()
  const [activeTab, setActiveTab] = useState<'rainwave' | 'apple'>('rainwave')

  // Auto-switch to active service
  useEffect(() => {
    if (source === 'rainwave' || source === 'apple') {
      setActiveTab(source)
    }
  }, [source])

  // Format duration
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Calculate progress
  const progress = currentTrack?.duration && currentTrack?.elapsed
    ? (currentTrack.elapsed / currentTrack.duration) * 100
    : 0

  return (
    <div className="bg-shark-920 text-chalk min-h-screen flex">
      {/* Sidebar Navigation */}
      <div className="w-64 bg-shark-960 p-4 space-y-2 border-r border-shark-800">
        <h2 className="font-caps text-lg font-bold mb-4 text-shark-400">Music Services</h2>

        <button
          onClick={() => setActiveTab('rainwave')}
          className={cn(
            "w-full text-left px-4 py-3 rounded-lg transition-all",
            "hover:bg-shark-900",
            activeTab === 'rainwave'
              ? "bg-shark-880 text-chalk border-l-4 border-sky"
              : "text-shark-400"
          )}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">Rainwave</div>
              <div className="text-xs opacity-75">Game Remix Radio</div>
            </div>
            {source === 'rainwave' && isPlaying && (
              <div className="size-2 bg-lime rounded-full animate-pulse" />
            )}
          </div>
        </button>

        <button
          onClick={() => setActiveTab('apple')}
          className={cn(
            "w-full text-left px-4 py-3 rounded-lg transition-all",
            "hover:bg-shark-900",
            activeTab === 'apple'
              ? "bg-shark-880 text-chalk border-l-4 border-rose"
              : "text-shark-400"
          )}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">Apple Music</div>
              <div className="text-xs opacity-75">Local Library</div>
            </div>
            {source === 'apple' && isPlaying && (
              <div className="size-2 bg-lime rounded-full animate-pulse" />
            )}
          </div>
        </button>

        {/* Connection Status */}
        <div className="pt-4 mt-4 border-t border-shark-800">
          <div className="text-xs text-shark-500">Connection Status</div>
          <div className="flex items-center gap-2 mt-1">
            <div className={cn(
              "size-2 rounded-full",
              isConnected ? "bg-lime" : "bg-shark-600"
            )} />
            <span className="text-sm text-shark-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-8">
        {activeTab === 'rainwave' ? (
          <RainwaveView
            currentTrack={currentTrack}
            progress={progress}
            upcoming={upcoming}
            history={history}
            formatTime={formatTime}
          />
        ) : (
          <AppleMusicView
            currentTrack={currentTrack}
            previousTrack={previousTrack}
            isPlaying={isPlaying}
            progress={progress}
            formatTime={formatTime}
          />
        )}
      </div>
    </div>
  )
}

// Rainwave View Component
function RainwaveView({ currentTrack, progress, upcoming, history, formatTime }: RainwaveViewProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-6 shadow-xl/50 inset-ring-2 inset-ring-white/10">
        <h1 className="font-caps text-3xl font-bold mb-2">Rainwave</h1>
        <p className="text-shark-400">Video Game Remix Radio</p>
      </div>

      {/* Now Playing */}
      <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-6 shadow-xl/50 inset-ring-2 inset-ring-white/10">
        <h2 className="font-caps text-xl font-bold mb-4">Now Playing</h2>

        {currentTrack ? (
          <div className="space-y-4">
            <div className="flex gap-4">
              {currentTrack.artwork && (
                <img
                  src={currentTrack.artwork}
                  alt={currentTrack.album}
                  className="size-32 rounded-lg shadow-lg"
                />
              )}
              <div className="flex-1 space-y-2">
                <div className="text-3xl font-bold">{currentTrack.title}</div>
                <div className="text-xl text-sky">{currentTrack.artist}</div>
                <div className="text-shark-400">
                  {isRainwaveData(currentTrack) && currentTrack.game && (
                    <div>🎮 {currentTrack.game}</div>
                  )}
                </div>
                {isRainwaveData(currentTrack) && currentTrack.requested_by && (
                  <div className={cn(
                    "text-sm",
                    currentTrack.is_crusader ? "text-yellow-400 font-semibold" : "text-blue-400"
                  )}>
                    {currentTrack.is_crusader ? "⚔️ Crusader" : "📻 Requested by"} {currentTrack.requested_by}
                  </div>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            {currentTrack.duration && currentTrack.duration > 0 && (
              <div className="space-y-1">
                <div className="bg-shark-800 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-sky h-full transition-all duration-1000 ease-linear"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-shark-400">
                  <span>{formatTime(currentTrack.elapsed || 0)}</span>
                  <span>{formatTime(currentTrack.duration || 0)}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-shark-600 italic">No music playing</div>
        )}
      </div>

      {/* Two Column Layout for Queue and History */}
      <div className="grid grid-cols-2 gap-6">
        {/* Coming Up */}
        {upcoming && upcoming.length > 0 && (
          <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-6 shadow-xl/50 inset-ring-2 inset-ring-white/10">
            <h2 className="font-caps text-xl font-bold mb-4">Coming Up</h2>
            <div className="space-y-3">
              {upcoming.slice(0, 6).map((item, index) => (
                <div key={index} className="p-3 bg-shark-900 rounded">
                  {isRainwaveElection(item) ? (
                    <div>
                      <p className="font-semibold text-yellow-400 mb-2">
                        {index === 0 ? '🗳️ Vote Now!' : '⏳ Election'}
                      </p>
                      <div className="space-y-2 ml-2">
                        {item.songs.slice(0, 3).map((song, songIndex) => (
                          <div key={songIndex} className="text-xs">
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <p className="text-chalk">{song.title}</p>
                                <p className="text-shark-500">{song.artist}</p>
                                {song.requested_by && (
                                  <p className={song.is_crusader ? "text-yellow-400 font-semibold" : "text-blue-400"}>
                                    {song.is_crusader ? "⚔️" : "req:"} {song.requested_by}
                                  </p>
                                )}
                              </div>
                              {item.voting_allowed && song.votes !== undefined && (
                                <span className="text-shark-400 ml-2">{song.votes}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="text-sm font-medium">{item.title}</p>
                      <p className="text-xs text-shark-400">by {item.artist}</p>
                      {item.requested_by && (
                        <p className="text-xs text-blue-400">req: {item.requested_by}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Previously Played */}
        {history && history.length > 0 && (
          <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-6 shadow-xl/50 inset-ring-2 inset-ring-white/10">
            <h2 className="font-caps text-xl font-bold mb-4">Previously Played</h2>
            <div className="space-y-2">
              {history.slice(0, 5).map((item, index) => {
                const track = isRainwaveElection(item) && item.songs.length > 0 ? item.songs[0] : item
                return (
                  <div key={index} className="p-2 bg-shark-900 rounded">
                    <p className="text-sm">{track.title}</p>
                    <p className="text-xs text-shark-400">by {track.artist}</p>
                    {track.requested_by && (
                      <p className={cn(
                        "text-xs",
                        track.is_crusader ? "text-yellow-400 font-semibold" : "text-blue-400"
                      )}>
                        {track.is_crusader ? "⚔️" : "req:"} {track.requested_by}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Apple Music View Component
function AppleMusicView({ currentTrack, previousTrack, isPlaying, progress, formatTime }: AppleMusicViewProps) {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-6 shadow-xl/50 inset-ring-2 inset-ring-white/10">
        <h1 className="font-caps text-3xl font-bold mb-2">Apple Music</h1>
        <p className="text-shark-400">Local Library Playback</p>
      </div>

      {/* Now Playing - Centered Simple View */}
      <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-8 shadow-xl/50 inset-ring-2 inset-ring-white/10">
        {currentTrack ? (
          <div className="space-y-6">
            {/* Album Art */}
            {currentTrack.artwork && (
              <div className="flex justify-center">
                <img
                  src={currentTrack.artwork}
                  alt={currentTrack.album}
                  className="size-64 rounded-xl shadow-2xl"
                />
              </div>
            )}

            {/* Track Info */}
            <div className="text-center space-y-2">
              <div className="text-3xl font-bold">{currentTrack.title}</div>
              <div className="text-xl text-rose-400">{currentTrack.artist}</div>
              {currentTrack.album && (
                <div className="text-shark-400">{currentTrack.album}</div>
              )}
            </div>

            {/* Progress Bar */}
            {currentTrack.duration && currentTrack.duration > 0 && (
              <div className="space-y-2">
                <div className="bg-shark-800 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-rose-500 to-rose-400 h-full transition-all duration-1000 ease-linear"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between text-sm text-shark-400">
                  <span>{formatTime(currentTrack.elapsed || 0)}</span>
                  <span>{formatTime(currentTrack.duration || 0)}</span>
                </div>
              </div>
            )}

            {/* Playback Status */}
            <div className="flex justify-center">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "size-3 rounded-full",
                  isPlaying ? "bg-lime animate-pulse" : "bg-shark-600"
                )} />
                <span className="text-shark-400">
                  {isPlaying ? 'Playing' : 'Paused'}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="text-shark-600 italic text-lg">No music playing</div>
            <div className="text-shark-700 text-sm mt-2">Start playback in Apple Music</div>
          </div>
        )}
      </div>

      {/* Previous Track */}
      {previousTrack && (
        <div className="from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-4 shadow-xl/50 inset-ring-2 inset-ring-white/10">
          <h3 className="text-sm font-caps text-shark-500 mb-2">Previous</h3>
          <div className="flex items-center gap-3">
            {previousTrack.artwork && (
              <img
                src={previousTrack.artwork}
                alt={previousTrack.album}
                className="size-12 rounded"
              />
            )}
            <div className="flex-1">
              <div className="font-semibold">{previousTrack.title}</div>
              <div className="text-sm text-shark-400">{previousTrack.artist}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}