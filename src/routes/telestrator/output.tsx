import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useRef, useCallback } from 'react'
import { serverConnection } from '@/hooks/use-server'
import type { MessageType } from '@/types/server'
import type { TelestratorDrawData, TelestratorPoint } from '@/types/telestrator'

export const Route = createFileRoute('/telestrator/output')({
  component: TelestratorOutput,
})

interface Stroke {
  id: string
  points: TelestratorPoint[]
  color: string
  width: number
  done: boolean
}

function TelestratorOutput() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const strokesRef = useRef<Map<string, Stroke>>(new Map())
  const completedOrderRef = useRef<string[]>([])

  const redraw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    strokesRef.current.forEach((stroke) => {
      if (stroke.points.length < 2) return

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
    })
  }, [])

  useEffect(() => {
    const handleDraw = (data: unknown) => {
      const drawData = data as TelestratorDrawData
      const existing = strokesRef.current.get(drawData.id)

      if (existing) {
        existing.points = existing.points.concat(drawData.points)
        existing.done = drawData.done
      } else {
        strokesRef.current.set(drawData.id, {
          id: drawData.id,
          points: [...drawData.points],
          color: drawData.color,
          width: drawData.width,
          done: drawData.done,
        })
      }

      if (drawData.done) {
        completedOrderRef.current.push(drawData.id)
      }

      redraw()
    }

    const handleUndo = () => {
      const lastId = completedOrderRef.current.pop()
      if (lastId) {
        strokesRef.current.delete(lastId)
        redraw()
      }
    }

    const handleClear = () => {
      strokesRef.current.clear()
      completedOrderRef.current = []
      redraw()
    }

    const drawType = 'telestrator:draw' as MessageType
    const undoType = 'telestrator:undo' as MessageType
    const clearType = 'telestrator:clear' as MessageType

    serverConnection.subscribe(drawType, handleDraw as any)
    serverConnection.subscribe(undoType, handleUndo as any)
    serverConnection.subscribe(clearType, handleClear as any)

    return () => {
      serverConnection.unsubscribe(drawType, handleDraw as any)
      serverConnection.unsubscribe(undoType, handleUndo as any)
      serverConnection.unsubscribe(clearType, handleClear as any)
    }
  }, [redraw])

  return (
    <canvas
      ref={canvasRef}
      width={1920}
      height={1080}
      className="block"
      style={{ background: 'transparent' }}
    />
  )
}
