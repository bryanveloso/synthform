import { useEffect, useState, useRef, useCallback } from 'react'
import { getEmoteName } from '@/config/emotes'

interface SpriteFrame {
  filename: string
  frame: { x: number; y: number; w: number; h: number }
  rotated: boolean
  trimmed: boolean
  spriteSourceSize: { x: number; y: number; w: number; h: number }
  sourceSize: { w: number; h: number }
}

interface SpriteSheetData {
  frames: Record<string, SpriteFrame>
  meta: {
    image: string
    size: { w: number; h: number }
    scale: string
  }
}

interface EmoteSpriteData {
  frame: SpriteFrame
  width: number
  height: number
}

export function useEmoteSpriteSheet() {
  const [spriteSheet, setSpriteSheet] = useState<SpriteSheetData | null>(null)
  const [spriteImage, setSpriteImage] = useState<HTMLImageElement | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const emoteDataCache = useRef<Map<string, EmoteSpriteData | null>>(new Map())

  useEffect(() => {
    let mounted = true

    async function loadSpriteSheet() {
      try {
        // Load sprite sheet JSON
        const response = await fetch('/emotes.json')
        const data: SpriteSheetData = await response.json()

        if (!mounted) return

        // Load sprite sheet image
        const img = new Image()
        img.onload = () => {
          if (mounted) {
            setSpriteImage(img)
            setSpriteSheet(data)
            setIsLoaded(true)
          }
        }
        img.onerror = () => {
          console.error('[SpriteSheet] Failed to load sprite image')
        }
        img.src = '/emotes.png'
      } catch (error) {
        console.error('[SpriteSheet] Failed to load sprite data:', error)
      }
    }

    loadSpriteSheet()

    return () => {
      mounted = false
    }
  }, [])

  // Get sprite data for an emote ID
  const getEmoteData = useCallback((emoteId: string): EmoteSpriteData | null => {
    // Check cache first
    if (emoteDataCache.current.has(emoteId)) {
      return emoteDataCache.current.get(emoteId)!
    }

    if (!spriteSheet || !isLoaded) {
      emoteDataCache.current.set(emoteId, null)
      return null
    }

    // Get emote name from ID
    const emoteName = getEmoteName(emoteId)
    if (!emoteName) {
      emoteDataCache.current.set(emoteId, null)
      return null
    }

    // Look up frame by filename (emoteName + .png)
    const filename = `${emoteName}.png`
    const frame = spriteSheet.frames[filename]

    if (!frame) {
      emoteDataCache.current.set(emoteId, null)
      return null
    }

    // Calculate scaled dimensions (sprite sheet is at 300x300, we render at 56x56)
    // Use the trimmed size for accurate collision
    const scale = 56 / 300
    const width = frame.spriteSourceSize.w * scale
    const height = frame.spriteSourceSize.h * scale

    const data: EmoteSpriteData = {
      frame,
      width,
      height
    }

    emoteDataCache.current.set(emoteId, data)
    return data
  }, [spriteSheet, isLoaded])

  // Check if an emote is in the sprite sheet
  const hasEmote = useCallback((emoteId: string): boolean => {
    return getEmoteData(emoteId) !== null
  }, [getEmoteData])

  return {
    spriteSheet,
    spriteImage,
    isLoaded,
    getEmoteData,
    hasEmote
  }
}