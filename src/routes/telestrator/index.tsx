import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useRef, useState, useCallback } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import { serverConnection } from '@/hooks/use-server'
import { useOBSScreenshot } from '@/hooks/use-obs-screenshot'
import type { TelestratorPoint } from '@/types/telestrator'

export const Route = createFileRoute('/telestrator/')({
  component: TelestratorInput,
})

const COLORS = [
  '#ffffff',
  '#ef4444',
  '#f59e0b',
  '#22c55e',
  '#3b82f6',
  '#a855f7',
  '#ec4899',
]

const WIDTHS = [3, 6, 10, 16]

const FLUSH_INTERVAL = 50 // ms

interface LocalStroke {
  id: string
  points: TelestratorPoint[]
  color: string
  width: number
}

function TelestratorInput() {
  const isConnected = useRealtimeStore((s) => s.isConnected)
  const { imageUrl: obsScreenshot, isConnected: obsConnected } = useOBSScreenshot(null, 5000)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [color, setColor] = useState('#ef4444')
  const [width, setWidth] = useState(6)
  const [showBackground, setShowBackground] = useState(true)

  // Drawing state (refs to avoid re-renders during drawing)
  const isDrawingRef = useRef(false)
  const currentStrokeRef = useRef<LocalStroke | null>(null)
  const pointBufferRef = useRef<TelestratorPoint[]>([])
  const flushTimerRef = useRef<number | null>(null)
  const strokesRef = useRef<LocalStroke[]>([])

  // Stable refs for current tool settings
  const colorRef = useRef(color)
  const widthRef = useRef(width)
  colorRef.current = color
  widthRef.current = width

  const redraw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const allStrokes = [...strokesRef.current]
    if (currentStrokeRef.current) {
      allStrokes.push(currentStrokeRef.current)
    }

    for (const stroke of allStrokes) {
      if (stroke.points.length < 2) continue

      ctx.beginPath()
      ctx.strokeStyle = stroke.color
      ctx.lineWidth = stroke.width
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'

      const first = stroke.points[0]
      ctx.moveTo(first.x * canvas.width, first.y * canvas.height)

      for (let i = 1; i < stroke.points.length; i++) {
        const point = stroke.points[i]
        ctx.lineTo(point.x * canvas.width, point.y * canvas.height)
      }

      ctx.stroke()
    }
  }, [])

  const flushPoints = useCallback(() => {
    const stroke = currentStrokeRef.current
    const buffer = pointBufferRef.current
    if (!stroke || buffer.length === 0) return

    serverConnection.send('telestrator:draw', {
      id: stroke.id,
      points: buffer,
      color: stroke.color,
      width: stroke.width,
      done: false,
    })

    pointBufferRef.current = []
  }, [])

  const normalizePoint = useCallback((e: PointerEvent): TelestratorPoint => {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    }
  }, [])

  const handlePointerDown = useCallback(
    (e: PointerEvent) => {
      const canvas = canvasRef.current
      if (!canvas) return

      canvas.setPointerCapture(e.pointerId)
      isDrawingRef.current = true

      const point = normalizePoint(e)
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

      currentStrokeRef.current = {
        id,
        points: [point],
        color: colorRef.current,
        width: widthRef.current,
      }
      pointBufferRef.current = [point]

      // Start flush interval
      flushTimerRef.current = window.setInterval(flushPoints, FLUSH_INTERVAL)

      redraw()
    },
    [normalizePoint, flushPoints, redraw],
  )

  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      if (!isDrawingRef.current || !currentStrokeRef.current) return

      const point = normalizePoint(e)
      currentStrokeRef.current.points.push(point)
      pointBufferRef.current.push(point)

      redraw()
    },
    [normalizePoint, redraw],
  )

  const handlePointerUp = useCallback(() => {
    if (!isDrawingRef.current || !currentStrokeRef.current) return

    isDrawingRef.current = false

    // Stop flush interval
    if (flushTimerRef.current !== null) {
      clearInterval(flushTimerRef.current)
      flushTimerRef.current = null
    }

    const stroke = currentStrokeRef.current

    // Send final batch with done flag
    serverConnection.send('telestrator:draw', {
      id: stroke.id,
      points: pointBufferRef.current,
      color: stroke.color,
      width: stroke.width,
      done: true,
    })

    pointBufferRef.current = []
    strokesRef.current.push(stroke)
    currentStrokeRef.current = null
  }, [])

  const handleUndo = useCallback(() => {
    if (strokesRef.current.length === 0) return
    strokesRef.current.pop()
    serverConnection.send('telestrator:undo', {} as any)
    redraw()
  }, [redraw])

  const handleClear = useCallback(() => {
    strokesRef.current = []
    currentStrokeRef.current = null
    serverConnection.send('telestrator:clear', {} as any)
    redraw()
  }, [redraw])

  // Set up canvas sizing and pointer events
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Prevent default touch handling on iPadOS Safari so pointer events fire
    const preventTouch = (e: TouchEvent) => e.preventDefault()
    canvas.addEventListener('touchstart', preventTouch, { passive: false })
    canvas.addEventListener('touchmove', preventTouch, { passive: false })

    canvas.addEventListener('pointerdown', handlePointerDown)
    canvas.addEventListener('pointermove', handlePointerMove)
    canvas.addEventListener('pointerup', handlePointerUp)
    canvas.addEventListener('pointercancel', handlePointerUp)

    return () => {
      canvas.removeEventListener('touchstart', preventTouch)
      canvas.removeEventListener('touchmove', preventTouch)
      canvas.removeEventListener('pointerdown', handlePointerDown)
      canvas.removeEventListener('pointermove', handlePointerMove)
      canvas.removeEventListener('pointerup', handlePointerUp)
      canvas.removeEventListener('pointercancel', handlePointerUp)

      if (flushTimerRef.current !== null) {
        clearInterval(flushTimerRef.current)
      }
    }
  }, [handlePointerDown, handlePointerMove, handlePointerUp])

  // Resize canvas to fit container while maintaining 16:9
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const resize = () => {
      const { width: cw, height: ch } = container.getBoundingClientRect()
      const aspect = 16 / 9
      let w = cw
      let h = cw / aspect
      if (h > ch) {
        h = ch
        w = ch * aspect
      }
      canvas.width = w
      canvas.height = h
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      redraw()
    }

    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [redraw])

  return (
    <div className="flex h-screen w-screen flex-col bg-shark-950 text-chalk select-none">
      {/* Toolbar */}
      <div className="flex items-center gap-4 border-b border-shark-800 px-4 py-3">
        {/* Connection indicator */}
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`}
          />
          <span className="text-xs text-shark-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        <div className="h-6 w-px bg-shark-700" />

        {/* Colors */}
        <div className="flex items-center gap-1.5">
          {COLORS.map((c) => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className={`h-8 w-8 rounded-full border-2 transition-transform ${
                color === c ? 'scale-110 border-chalk' : 'border-transparent'
              }`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>

        <div className="h-6 w-px bg-shark-700" />

        {/* Widths */}
        <div className="flex items-center gap-1.5">
          {WIDTHS.map((w) => (
            <button
              key={w}
              onClick={() => setWidth(w)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg border-2 transition-transform ${
                width === w
                  ? 'scale-110 border-chalk bg-shark-800'
                  : 'border-transparent bg-shark-900'
              }`}
            >
              <span
                className="rounded-full bg-chalk"
                style={{ width: w, height: w }}
              />
            </button>
          ))}
        </div>

        <div className="h-6 w-px bg-shark-700" />

        {/* Actions */}
        <button
          onClick={handleUndo}
          className="rounded-lg bg-shark-800 px-4 py-2 text-sm font-medium text-chalk transition-colors hover:bg-shark-700 active:bg-shark-600"
        >
          Undo
        </button>
        <button
          onClick={handleClear}
          className="rounded-lg bg-red-900/60 px-4 py-2 text-sm font-medium text-red-300 transition-colors hover:bg-red-900/80 active:bg-red-800"
        >
          Clear
        </button>

        <div className="h-6 w-px bg-shark-700" />

        {/* OBS background toggle */}
        <button
          onClick={() => setShowBackground((v) => !v)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            showBackground && obsConnected
              ? 'bg-sky/20 text-sky'
              : 'bg-shark-800 text-shark-400 hover:bg-shark-700'
          }`}
        >
          BG {showBackground && obsConnected ? 'ON' : 'OFF'}
        </button>

        {/* OBS status */}
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${obsConnected ? 'bg-sky' : 'bg-shark-600'}`}
          />
          <span className="text-xs text-shark-400">OBS</span>
        </div>
      </div>

      {/* Canvas area */}
      <div
        ref={containerRef}
        className="relative flex flex-1 items-center justify-center bg-shark-920 p-4"
      >
        <div className="relative">
          {showBackground && obsScreenshot && (
            <img
              src={obsScreenshot}
              alt=""
              className="pointer-events-none absolute inset-0 size-full rounded-lg object-cover opacity-40"
            />
          )}
          <canvas
            ref={canvasRef}
            className="relative cursor-crosshair rounded-lg"
            style={{ touchAction: 'none' }}
          />
        </div>
      </div>
    </div>
  )
}
