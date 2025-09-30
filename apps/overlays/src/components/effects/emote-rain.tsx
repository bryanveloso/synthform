import { useEffect, useRef, useState, useCallback, memo } from 'react'
import Matter from 'matter-js'

import { useChatMessages } from '@/hooks/use-chat-messages'
import { useEmoteSpriteSheet } from '@/hooks/use-emote-sprite-sheet'

import { emoteManager } from './emote-manager'

interface EmoteBody {
  id: string
  emoteId: string
  body: Matter.Body
  imageLoaded: boolean
  width: number
  height: number
  isFromSpriteSheet: boolean
}

export const EmoteRain = memo(function EmoteRain() {
  const sceneRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<Matter.Engine | null>(null)
  const emoteBodiesRef = useRef<Map<string, EmoteBody>>(new Map())
  const emoteImagesRef = useRef<Map<string, HTMLImageElement>>(new Map())
  const timeoutIdsRef = useRef<Set<NodeJS.Timeout>>(new Set())
  const abortControllerRef = useRef<AbortController | null>(null)
  const [debugInfo, setDebugInfo] = useState({ emoteCount: 0 })

  const { spriteImage, getEmoteData, isLoaded: spriteLoaded } = useEmoteSpriteSheet()

  // Initialize Matter.js
  useEffect(() => {
    if (!sceneRef.current) return

    // Create abort controller for event listeners
    abortControllerRef.current = new AbortController()

    // Create engine with optimizations for many bodies
    const engine = Matter.Engine.create()
    engine.gravity.scale = 0.0008 // Adjust gravity strength

    // Enable sleeping to reduce jitter when emotes pile up
    engine.enableSleeping = true

    engineRef.current = engine

    // Create boundaries (ground at actual bottom of viewport)
    const ground = Matter.Bodies.rectangle(960, 1110, 1920, 60, { isStatic: true })
    const leftWall = Matter.Bodies.rectangle(-30, 540, 60, 1080, { isStatic: true })
    const rightWall = Matter.Bodies.rectangle(1950, 540, 60, 1080, { isStatic: true })

    Matter.Composite.add(engine.world, [ground, leftWall, rightWall])

    // Create runner (physics only, no renderer)
    const runner = Matter.Runner.create()
    Matter.Runner.run(runner, engine)

    // Create our own canvas for rendering
    const canvas = document.createElement('canvas')
    canvas.width = 1920
    canvas.height = 1080
    canvas.style.position = 'absolute'
    canvas.style.top = '0'
    canvas.style.left = '0'
    canvas.style.width = '1920px'
    canvas.style.height = '1080px'
    canvas.style.pointerEvents = 'none'
    sceneRef.current.appendChild(canvas)

    const ctx = canvas.getContext('2d')!
    const toRemove: string[] = []
    let animationFrameId: number

    const renderEmotes = () => {
      // Clear canvas
      ctx.clearRect(0, 0, 1920, 1080)

      // Clear removal list
      toRemove.length = 0

      // Draw each emote
      emoteBodiesRef.current.forEach((emoteBody) => {
        const { position, angle } = emoteBody.body

        // Mark for removal if off screen
        if (position.y > 1200) {
          toRemove.push(emoteBody.id)
          return
        }

        ctx.save()
        ctx.translate(position.x, position.y)
        ctx.rotate(angle)

        if (emoteBody.isFromSpriteSheet && spriteImage) {
          // Draw from sprite sheet
          const emoteData = getEmoteData(emoteBody.emoteId)
          if (emoteData) {
            const { frame } = emoteData
            ctx.drawImage(
              spriteImage,
              frame.frame.x, frame.frame.y, frame.frame.w, frame.frame.h,
              -emoteBody.width / 2, -emoteBody.height / 2,
              emoteBody.width, emoteBody.height
            )
          }
        } else {
          // Draw from cached image (Twitch CDN)
          const img = emoteImagesRef.current.get(emoteBody.emoteId)
          if (!img || !emoteBody.imageLoaded) {
            ctx.restore()
            return
          }
          ctx.drawImage(img, -emoteBody.width / 2, -emoteBody.height / 2, emoteBody.width, emoteBody.height)
        }

        ctx.restore()
      })

      // Remove off-screen emotes in batch
      if (toRemove.length > 0 && engineRef.current) {
        const bodiesToRemove = toRemove
          .map(id => {
            const emoteBody = emoteBodiesRef.current.get(id)
            if (emoteBody) {
              emoteBodiesRef.current.delete(id)
              return emoteBody.body
            }
            return null
          })
          .filter(body => body !== null) as Matter.Body[]

        if (bodiesToRemove.length > 0) {
          Matter.Composite.remove(engineRef.current.world, bodiesToRemove)
        }
      }

      animationFrameId = requestAnimationFrame(renderEmotes)
    }

    animationFrameId = requestAnimationFrame(renderEmotes)

    return () => {
      // Clear all pending timeouts
      timeoutIdsRef.current.forEach(clearTimeout)
      timeoutIdsRef.current.clear()

      // Clear image cache
      emoteImagesRef.current.clear()

      // Abort all event listeners
      abortControllerRef.current?.abort()

      // Cancel animation frame
      cancelAnimationFrame(animationFrameId)

      Matter.Runner.stop(runner)
      Matter.World.clear(engine.world, false)
      Matter.Engine.clear(engine)
      canvas.remove()
    }
  }, [])

  // Preload emote image
  const preloadEmote = useCallback((emoteId: string, emoteBodyId?: string) => {
    // Check if this emote is in the sprite sheet
    const spriteData = getEmoteData(emoteId)
    if (spriteData && spriteLoaded) {
      // Emote is in sprite sheet, mark as loaded immediately
      if (emoteBodyId) {
        const emoteBody = emoteBodiesRef.current.get(emoteBodyId)
        if (emoteBody) {
          emoteBody.imageLoaded = true
        }
      }
      return null
    }

    // If image already cached and loaded, return it
    const existingImg = emoteImagesRef.current.get(emoteId)
    if (existingImg) {
      // Move to end for LRU behavior
      emoteImagesRef.current.delete(emoteId)
      emoteImagesRef.current.set(emoteId, existingImg)

      if (existingImg.complete) {
        // Image already loaded, immediately mark the body as loaded if ID provided
        if (emoteBodyId) {
          const emoteBody = emoteBodiesRef.current.get(emoteBodyId)
          if (emoteBody) {
            emoteBody.imageLoaded = true
          }
        }
        return existingImg
      }
    }

    // Create new image if not cached
    if (!existingImg) {
      const img = new Image()

      // Check if this is a template ID (starts with "emotesv2_") or numeric ID
      const isTemplateId = emoteId.startsWith('emotesv2_')

      // Both animated and static emotes use "default" in v2 API
      // The server automatically provides the animated version if it exists
      img.src = `https://static-cdn.jtvnw.net/emoticons/v2/${emoteId}/default/dark/2.0`

      img.onload = () => {
        // Update ALL bodies with this emote ID
        emoteBodiesRef.current.forEach((body) => {
          if (body.emoteId === emoteId) {
            body.imageLoaded = true
          }
        })
      }

      // Try fallbacks if loading fails
      let fallbackAttempted = false
      img.onerror = () => {
        // For template IDs (v2 emotes), there's no v1 fallback
        // For numeric IDs, try v1 API as fallback
        if (!isTemplateId && !fallbackAttempted) {
          fallbackAttempted = true
          img.src = `https://static-cdn.jtvnw.net/emoticons/v1/${emoteId}/2.0`
        } else {
          // Failed to load - clean up all bodies with this emote ID
          emoteBodiesRef.current.forEach((body) => {
            if (body.emoteId === emoteId && engineRef.current) {
              Matter.Composite.remove(engineRef.current.world, body.body)
              emoteBodiesRef.current.delete(body.id)
            }
          })
          emoteImagesRef.current.delete(emoteId)
        }
      }

      emoteImagesRef.current.set(emoteId, img)

      // Simple cache limit - remove oldest if over 50 images
      if (emoteImagesRef.current.size > 50) {
        const firstKey = emoteImagesRef.current.keys().next().value
        if (firstKey) emoteImagesRef.current.delete(firstKey)
      }

      return img
    }

    // Image exists but still loading - mark this specific body when it loads
    if (emoteBodyId && abortControllerRef.current) {
      existingImg.addEventListener('load', () => {
        const emoteBody = emoteBodiesRef.current.get(emoteBodyId)
        if (emoteBody) {
          emoteBody.imageLoaded = true
        }
      }, { once: true, signal: abortControllerRef.current.signal })
    }

    return existingImg
  }, [getEmoteData, spriteLoaded])

  // Remove an emote
  const removeEmote = useCallback((id: string) => {
    const emoteBody = emoteBodiesRef.current.get(id)
    if (!emoteBody || !engineRef.current) return

    Matter.Composite.remove(engineRef.current.world, emoteBody.body)
    emoteBodiesRef.current.delete(id)
  }, [])

  // Spawn an emote
  const spawnEmote = useCallback((emoteId: string) => {
    if (!engineRef.current) return

    // Random position across top
    const x = Math.random() * 1920
    const y = -50

    // Check if emote is in sprite sheet to get accurate dimensions
    const spriteData = getEmoteData(emoteId)
    let width = 56
    let height = 56
    let isFromSpriteSheet = false
    let body: Matter.Body

    if (spriteData && spriteLoaded) {
      // Use actual emote dimensions from sprite sheet
      width = spriteData.width
      height = spriteData.height
      isFromSpriteSheet = true

      // Create rectangular body matching actual emote shape
      body = Matter.Bodies.rectangle(x, y, width, height, {
        restitution: 0.6,
        friction: 0.3,
        density: 0.001,
        sleepThreshold: 60,
        render: {
          visible: false
        }
      })
    } else {
      // Fallback to circular body for non-sprite sheet emotes
      body = Matter.Bodies.circle(x, y, 28, {
        restitution: 0.6,
        friction: 0.3,
        density: 0.001,
        sleepThreshold: 60,
        render: {
          visible: false
        }
      })
    }

    // Apply random horizontal velocity
    Matter.Body.setVelocity(body, {
      x: (Math.random() - 0.5) * 8,
      y: 0
    })

    // Apply random spin
    Matter.Body.setAngularVelocity(body, (Math.random() - 0.5) * 0.2)

    Matter.Composite.add(engineRef.current.world, body)

    // Track emote
    const emoteBody: EmoteBody = {
      id: `${emoteId}-${Date.now()}-${Math.random()}`,
      emoteId,
      body,
      imageLoaded: false,
      width,
      height,
      isFromSpriteSheet
    }

    emoteBodiesRef.current.set(emoteBody.id, emoteBody)

    // Preload image with the specific emote body ID
    preloadEmote(emoteId, emoteBody.id)

    // Remove ground collision after 45 seconds so emote falls off screen
    const timeoutId = setTimeout(() => {
      // Instead of removing immediately, let it fall by removing collision
      // The renderEmotes loop will clean it up when it goes off screen
      if (emoteBody.body && engineRef.current) {
        // Wake up any bodies that might be resting on this one
        // Recursively wake bodies to cascade through stacks
        const wokenBodies = new Set<Matter.Body>()
        const bodiesToCheck = [emoteBody.body]

        while (bodiesToCheck.length > 0) {
          const currentBody = bodiesToCheck.pop()!
          if (wokenBodies.has(currentBody)) continue
          wokenBodies.add(currentBody)

          // Find bodies near this one
          const nearbyBodies = Matter.Query.region(
            engineRef.current.world.bodies,
            {
              min: { x: currentBody.position.x - 60, y: currentBody.position.y - 60 },
              max: { x: currentBody.position.x + 60, y: currentBody.position.y + 60 }
            }
          )

          nearbyBodies.forEach(body => {
            if (!wokenBodies.has(body) && body !== emoteBody.body) {
              Matter.Sleeping.set(body, false)
              // Add to check list to cascade further
              bodiesToCheck.push(body)
            }
          })
        }

        // Wake up the body if it's sleeping
        Matter.Sleeping.set(emoteBody.body, false)
        // Make the body non-colliding so it falls through the ground
        emoteBody.body.collisionFilter.group = -1
        emoteBody.body.collisionFilter.mask = 0
        // Give it a small downward velocity to ensure it starts falling
        Matter.Body.setVelocity(emoteBody.body, {
          x: emoteBody.body.velocity.x,
          y: 2
        })
      }
      timeoutIdsRef.current.delete(timeoutId)
    }, 45000)
    timeoutIdsRef.current.add(timeoutId)
  }, [preloadEmote, getEmoteData, spriteLoaded])

  // Update debug info
  useEffect(() => {
    const interval = setInterval(() => {
      setDebugInfo({
        emoteCount: emoteBodiesRef.current.size
      })
    }, 500)

    return () => clearInterval(interval)
  }, [])

  // Handle emotes from chat
  const handleEmote = useCallback((emoteId: string, emoteSetId?: string) => {
    console.log('[EmoteRain] Received emote from chat:', emoteId, 'set:', emoteSetId)

    // Filter out global emotes (set_id "0" or undefined typically means global)
    // Channel emotes have specific set IDs like longer strings
    if (!emoteSetId || emoteSetId === "0") {
      console.log('[EmoteRain] Skipping global emote')
      return
    }

    emoteManager.queueEmote(emoteId)
  }, [])

  useChatMessages({
    onEmote: handleEmote
  })

  // Listen for emotes from the manager
  useEffect(() => {
    const handleEmote = (emoteId: string) => {
      console.log('[EmoteRain] Manager emitted emote:', emoteId)
      spawnEmote(emoteId)
    }

    emoteManager.on('emote', handleEmote)
    console.log('[EmoteRain] Registered listener with emoteManager')

    return () => {
      emoteManager.off('emote', handleEmote)
    }
  }, [spawnEmote])

  // Debug UI
  const isDev = import.meta.env.DEV

  return (
    <>
      <div
        ref={sceneRef}
        className="pointer-events-none fixed inset-0"
        style={{ zIndex: 9999 }}
      />

      {isDev && (
        <div className="fixed bottom-4 right-4 z-[10000] space-y-2 rounded bg-black/80 p-3 text-xs text-white">
          <div className="font-bold text-yellow-400">🎮 Emote Rain Debug</div>
          <div>Active: {debugInfo.emoteCount}/300</div>
          <div className="flex gap-2">
            <button
              className="rounded bg-blue-600 px-2 py-1 hover:bg-blue-700"
              onClick={() => {
                const testEmotes = [
                  '300354391',
                  '300354394',
                  '300354469',
                  '300359180',
                  '300488581'
                ]
                testEmotes.forEach(id => emoteManager.queueEmote(id))
              }}>
              Spawn Test Emotes
            </button>
            <button
              className="rounded bg-purple-600 px-2 py-1 hover:bg-purple-700"
              onClick={() => {
                for (let i = 0; i < 20; i++) {
                  emoteManager.queueEmote('300354391')
                }
              }}>
              Emote Bomb!
            </button>
          </div>
        </div>
      )}
    </>
  )
})
