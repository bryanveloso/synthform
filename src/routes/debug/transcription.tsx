import { createFileRoute } from '@tanstack/react-router'
import { useState, useEffect, useRef, useCallback } from 'react'

export const Route = createFileRoute('/debug/transcription')({
  component: TranscriptionDebug,
})

interface TranscriptionLine {
  text: string
  start: string
  end: string
  speaker?: number
}

interface TranscriptionUpdate {
  lines?: TranscriptionLine[]
  buffer_transcription?: string
  status?: string
  type?: string
}

const WS_URL = 'ws://zelan:8765/debug'

function TranscriptionDebug() {
  const [isConnected, setIsConnected] = useState(false)
  const [lines, setLines] = useState<TranscriptionLine[]>([])
  const [buffer, setBuffer] = useState('')
  const [updateCount, setUpdateCount] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      setIsConnected(true)
    }

    ws.onclose = () => {
      setIsConnected(false)
      setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (event) => {
      try {
        const data: TranscriptionUpdate = JSON.parse(event.data)
        setUpdateCount((c) => c + 1)

        if (data.lines && data.lines.length > 0) {
          setLines(data.lines)
        }

        if (data.buffer_transcription !== undefined) {
          setBuffer(data.buffer_transcription)
        }
      } catch {
        // ignore parse errors
      }
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines, buffer])

  const fullText = lines.map((l) => l.text).join(' ')

  return (
    <div className="min-h-screen bg-black text-white p-8 font-mono">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl">Transcription Debug</h1>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-500">{updateCount} updates</span>
            <span
              className={`px-2 py-1 rounded text-xs ${isConnected ? 'bg-green-800 text-green-200' : 'bg-red-800 text-red-200'}`}
            >
              {isConnected ? 'Connected' : 'Reconnecting...'}
            </span>
          </div>
        </div>

        {/* Live caption preview — what closed captions would look like */}
        <div className="mb-8">
          <h2 className="text-sm text-gray-500 uppercase tracking-wide mb-2">Caption Preview</h2>
          <div className="bg-gray-900 rounded-lg p-6 min-h-[120px] flex items-end">
            <p className="text-xl leading-relaxed">
              {buffer || fullText || (
                <span className="text-gray-600">Waiting for speech...</span>
              )}
            </p>
          </div>
        </div>

        {/* Committed lines */}
        <div className="mb-8">
          <h2 className="text-sm text-gray-500 uppercase tracking-wide mb-2">
            Committed Lines ({lines.length})
          </h2>
          <div ref={scrollRef} className="bg-gray-900 rounded-lg p-4 max-h-96 overflow-y-auto">
            {lines.length > 0 ? (
              <div className="space-y-1">
                {lines.map((line, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="text-gray-600 shrink-0 w-24 text-right">
                      {line.start}
                    </span>
                    <span>{line.text}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-600">No committed lines yet.</p>
            )}
          </div>
        </div>

        {/* Buffer (partial / in-progress) */}
        {buffer && (
          <div>
            <h2 className="text-sm text-gray-500 uppercase tracking-wide mb-2">Buffer (in progress)</h2>
            <div className="bg-gray-900 rounded-lg p-4">
              <p className="text-yellow-400">{buffer}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
