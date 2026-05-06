import { useEffect, useRef, useState } from 'react'
import OBSWebSocket from 'obs-websocket-js'

const OBS_WS_URL = import.meta.env.VITE_OBS_WS_URL || 'ws://saya:4455'
const OBS_WS_PASSWORD = import.meta.env.VITE_OBS_WS_PASSWORD || ''

/**
 * Captures periodic screenshots from OBS via the WebSocket API.
 *
 * @param sourceName - OBS source or scene name to capture. Null to capture the current program scene.
 * @param intervalMs - Capture interval in milliseconds (default 5000).
 * @param imageFormat - Image format: "png" or "jpg" (default "jpg" for smaller payloads).
 * @param imageWidth - Output width (default 960, half of 1920 for performance).
 */
export function useOBSScreenshot(
  sourceName: string | null = null,
  intervalMs = 5000,
  imageFormat: 'png' | 'jpg' = 'jpg',
  imageWidth = 960,
) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const obsRef = useRef<OBSWebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const obs = new OBSWebSocket()
    obsRef.current = obs
    let destroyed = false

    async function connect() {
      try {
        await obs.connect(OBS_WS_URL, OBS_WS_PASSWORD || undefined)
        if (destroyed) return
        setIsConnected(true)
        setError(null)

        async function capture() {
          if (destroyed) return
          try {
            let result

            if (sourceName) {
              result = await obs.call('GetSourceScreenshot', {
                sourceName,
                imageFormat: `image/${imageFormat}`,
                imageWidth,
              })
            } else {
              const { currentProgramSceneName } = await obs.call('GetCurrentProgramScene')
              result = await obs.call('GetSourceScreenshot', {
                sourceName: currentProgramSceneName,
                imageFormat: `image/${imageFormat}`,
                imageWidth,
              })
            }

            if (!destroyed && result.imageData) {
              setImageUrl(result.imageData)
            }
          } catch {
            // Silently skip failed captures (OBS might be transitioning scenes)
          }
        }

        capture()
        timerRef.current = setInterval(capture, intervalMs)
      } catch (err) {
        if (!destroyed) {
          setError(err instanceof Error ? err.message : 'Failed to connect to OBS')
          setIsConnected(false)
        }
      }
    }

    connect()

    obs.on('ConnectionClosed', () => {
      if (!destroyed) {
        setIsConnected(false)
        if (timerRef.current) clearInterval(timerRef.current)
      }
    })

    return () => {
      destroyed = true
      if (timerRef.current) clearInterval(timerRef.current)
      obs.disconnect()
    }
  }, [sourceName, intervalMs, imageFormat, imageWidth])

  return { imageUrl, isConnected, error }
}
