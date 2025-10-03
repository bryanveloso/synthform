/**
 * Audio Preloader
 *
 * Preloads all alert sound files at app startup to eliminate audio loading latency.
 * Provides cached audio elements for instant playback.
 */

import { alertSoundConfig } from '@/config/sounds'

/**
 * Extract all sound file paths from sound config
 */
function extractSoundFiles(): string[] {
  const soundPaths = new Set<string>()

  for (const config of Object.values(alertSoundConfig)) {
    if (config.sounds) {
      for (const soundPath of Object.values(config.sounds)) {
        soundPaths.add(soundPath)
      }
    }
    if (config.defaultSound) {
      soundPaths.add(config.defaultSound)
    }
  }

  return Array.from(soundPaths)
}

const audioCache = new Map<string, HTMLAudioElement>()
let preloadComplete = false

/**
 * Preload all sound files into memory
 * Call once at app startup
 */
export function preloadSounds(): void {
  if (preloadComplete) return

  const soundFiles = extractSoundFiles()
  console.log('[Audio] Preloading sounds...')

  for (const soundPath of soundFiles) {
    try {
      const audio = new Audio(soundPath)
      audio.preload = 'auto'
      audioCache.set(soundPath, audio)
    } catch (error) {
      console.warn(`[Audio] Failed to preload ${soundPath}:`, error)
    }
  }

  preloadComplete = true
  console.log(`[Audio] Preloaded ${audioCache.size} sounds`)
}

/**
 * Get a preloaded audio element for playback
 * Returns null if sound not found in cache
 */
export function getPreloadedAudio(soundPath: string): HTMLAudioElement | null {
  if (!soundPath) return null

  const audio = audioCache.get(soundPath)
  if (!audio) {
    console.warn(`[Audio] Sound not preloaded: ${soundPath}`)
    return null
  }

  return audio
}

/**
 * Check if audio preloader is ready
 */
export function isPreloadComplete(): boolean {
  return preloadComplete
}
