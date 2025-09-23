import { useEffect, useRef } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import type { ChatMessage, EmoteFragment } from '@/types/server'

export type { ChatMessage, EmoteFragment }

interface UseChatMessagesOptions {
  onMessage?: (message: ChatMessage) => void
  onEmote?: (emoteId: string, emoteSetId?: string) => void
  maxMessages?: number
}

export function useChatMessages(options: UseChatMessagesOptions = {}) {
  const { onMessage, onEmote, maxMessages = 50 } = options
  const processedRef = useRef<Set<string>>(new Set())

  // Get chat messages from store - no useEffect, no store actions on mount
  const allMessages = useRealtimeStore((state) => state.chat.messages)
  const isConnected = useRealtimeStore((state) => state.isConnected)

  // Slice to requested max
  const messages = allMessages.slice(-maxMessages)
  const latestMessage = messages[messages.length - 1] || undefined

  // Process new messages with callbacks
  useEffect(() => {
    if (!latestMessage) return

    const messageKey = latestMessage.id || `${Date.now()}`

    // Skip if already processed
    if (processedRef.current.has(messageKey)) return
    processedRef.current.add(messageKey)

    // Call callbacks
    onMessage?.(latestMessage)

    // Process emotes
    if (onEmote && latestMessage.fragments) {
      latestMessage.fragments.forEach(fragment => {
        if (fragment.type === 'emote' && fragment.emote?.id) {
          onEmote(fragment.emote.id, fragment.emote.emote_set_id)
        }
      })
    }

    // Clean up old processed messages (keep last 100)
    if (processedRef.current.size > 100) {
      const entries = Array.from(processedRef.current)
      processedRef.current = new Set(entries.slice(-50))
    }
  }, [latestMessage, onMessage, onEmote])

  return {
    messages,
    latestMessage,
    messageCount: messages.length,
    isConnected
  }
}