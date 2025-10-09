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
const failedPreloads = new Set<string>()
let preloadComplete = false
let preloadPromise: Promise<void> | null = null

/**
 * Preload all sound files into memory
 * Returns a promise that resolves when all sounds are ready
 */
export function preloadSounds(): Promise<void> {
  if (preloadPromise) return preloadPromise

  const soundFiles = extractSoundFiles()
  console.log('[Audio] Preloading sounds...')

  if (soundFiles.length === 0) {
    preloadComplete = true
    console.log('[Audio] No sounds to preload.')
    preloadPromise = Promise.resolve()
    return preloadPromise
  }

  preloadPromise = Promise.all(
    soundFiles.map(
      (soundPath) =>
        new Promise<void>((resolve) => {
          try {
            const audio = new Audio(soundPath)
            audio.preload = 'auto'

            const onCanPlayThrough = () => {
              audio.removeEventListener('canplaythrough', onCanPlayThrough)
              audio.removeEventListener('error', onError)
              audioCache.set(soundPath, audio)
              resolve()
            }

            const onError = (e: Event | string) => {
              audio.removeEventListener('canplaythrough', onCanPlayThrough)
              audio.removeEventListener('error', onError)
              console.warn(`[Audio] Failed to preload ${soundPath}:`, e)
              failedPreloads.add(soundPath)
              resolve() // Don't block other sounds
            }

            audio.addEventListener('canplaythrough', onCanPlayThrough)
            audio.addEventListener('error', onError)
            audio.load()
          } catch (error) {
            console.warn(`[Audio] Failed to create Audio for ${soundPath}:`, error)
            failedPreloads.add(soundPath)
            resolve() // Don't block other sounds
          }
        })
    )
  ).then(() => {
    preloadComplete = true
    console.log(`[Audio] Preloaded ${audioCache.size} sounds`)
  })

  return preloadPromise
}

/**
 * Get a cloned audio element for playback
 * Clones the preloaded audio to allow multiple simultaneous playbacks
 * Returns null if sound not found in cache
 */
export function getPreloadedAudio(soundPath: string): HTMLAudioElement | null {
  if (!soundPath) return null

  // Don't warn about known failures
  if (failedPreloads.has(soundPath)) {
    return null
  }

  const cachedAudio = audioCache.get(soundPath)
  if (!cachedAudio) {
    // Only warn if preloading is complete
    if (preloadComplete) {
      console.warn(`[Audio] Sound not preloaded: ${soundPath}`)
    }
    return null
  }

  // Clone the audio element to allow multiple simultaneous playbacks
  // The browser will reuse the cached audio buffer
  const audio = new Audio(cachedAudio.src)
  audio.preload = 'auto'
  return audio
}

/**
 * Check if audio preloader is ready
 */
export function isPreloadComplete(): boolean {
  return preloadComplete
}
