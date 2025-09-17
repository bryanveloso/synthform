import { useEffect, useRef } from 'react'
import { useServer } from './use-server'
import type { ChatMessage, EmoteFragment } from '@/types/server'

export type { ChatMessage, EmoteFragment }

interface UseChatMessagesOptions {
  onMessage?: (message: ChatMessage) => void
  onEmote?: (emoteId: string, emoteSetId?: string) => void
}

export function useChatMessages(options: UseChatMessagesOptions = {}) {
  const { data } = useServer(['chat:message'] as const)
  const processedRef = useRef<Set<string>>(new Set())

  // Destructure callbacks to use directly in dependencies
  const { onMessage, onEmote } = options

  useEffect(() => {
    const chatMessage = data['chat:message']
    console.log('[useChatMessages] Raw message:', chatMessage)
    if (!chatMessage) return

    // The message IS the payload directly from the server
    const messageKey = `${chatMessage.id || Date.now()}`

    // Skip if we've already processed this message
    if (processedRef.current.has(messageKey)) return
    processedRef.current.add(messageKey)

    const message: ChatMessage = {
      id: messageKey,
      text: chatMessage.text || '',
      user_name: chatMessage.user_name || 'Unknown',
      user_display_name: chatMessage.user_display_name || chatMessage.user_name || 'Unknown',
      fragments: chatMessage.fragments || []
    }

    // Call the onMessage callback if provided
    onMessage?.(message)

    // Process emotes and call onEmote for each
    if (onEmote && message.fragments) {
      console.log('[useChatMessages] Processing fragments:', message.fragments)
      message.fragments.forEach(fragment => {
        console.log('[useChatMessages] Fragment:', fragment)
        if (fragment.type === 'emote' && fragment.emote?.id) {
          console.log('[useChatMessages] Found emote:', fragment.emote.id, 'set:', fragment.emote.emote_set_id)
          onEmote(fragment.emote.id, fragment.emote.emote_set_id)
        }
      })
    }

    // Clean up old processed messages (keep last 100)
    if (processedRef.current.size > 100) {
      const entries = Array.from(processedRef.current)
      processedRef.current = new Set(entries.slice(-50))
    }
  }, [data['chat:message'], onMessage, onEmote])

  return {
    latestMessage: data['chat:message'] as ChatMessage | undefined
  }
}