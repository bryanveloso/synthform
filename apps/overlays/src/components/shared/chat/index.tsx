import { useEffect, useRef } from 'react'

import { useChatMessages } from '@/hooks/use-chat-messages'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/types/server'

interface ChatProps {
  maxMessages?: number
  className?: string
  messageClassName?: string
  fadeOut?: boolean
  fadeOutDelay?: number
}

export function Chat({
  maxMessages = 20,
  className,
  messageClassName,
  fadeOut = true,
  fadeOutDelay = 30000, // 30 seconds
}: ChatProps) {
  const { messages } = useChatMessages({ maxMessages })
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div
      ref={containerRef}
      className={cn('flex flex-col gap-1 overflow-x-hidden overflow-y-auto', className)}>
      {messages.map((message, index) => (
        <ChatMessage
          key={message.id || `chat-msg-${index}`}
          message={message}
          className={messageClassName}
          fadeOut={fadeOut}
          fadeOutDelay={fadeOutDelay}
        />
      ))}
    </div>
  )
}

interface ChatMessageProps {
  message: ChatMessage
  className?: string
  fadeOut?: boolean
  fadeOutDelay?: number
}

function ChatMessage({
  message,
  className,
  fadeOut = true,
  fadeOutDelay = 30000,
}: ChatMessageProps) {
  const messageRef = useRef<HTMLDivElement>(null)

  // Fade out old messages
  useEffect(() => {
    if (!fadeOut || !messageRef.current) return

    const timer = setTimeout(() => {
      if (messageRef.current) {
        messageRef.current.style.opacity = '0.75'
      }
    }, fadeOutDelay)

    return () => clearTimeout(timer)
  }, [fadeOut, fadeOutDelay])

  return (
    <div
      ref={messageRef}
      className={cn('font-fira flex items-start transition-opacity duration-500', className)}>
      <div className="min-w-0 flex-1">
        <span className="inline-flex items-center gap-1">
          <span className="font-extrabold text-[#f7b500]">
            {message.user_display_name || message.user_name}:
          </span>
        </span>{' '}
        <MessageContent message={message} />
      </div>
    </div>
  )
}

interface MessageContentProps {
  message: ChatMessage
}

function MessageContent({ message }: MessageContentProps) {
  if (!message.fragments || message.fragments.length === 0) {
    return <span className="text-white/80">{message.text}</span>
  }

  return (
    <span className="text-white/80">
      {message.fragments.map((fragment, index) => {
        if (fragment.type === 'emote' && fragment.emote) {
          // Render Twitch emote
          return (
            <img
              key={`${fragment.emote.id}-${index}`}
              src={`https://static-cdn.jtvnw.net/emoticons/v2/${fragment.emote.id}/default/dark/3.0`}
              alt={fragment.text}
              className="mx-0.5 inline-block h-6 w-auto align-middle"
              loading="lazy"
            />
          )
        }
        // Regular text
        return <span key={index}>{fragment.text}</span>
      })}
    </span>
  )
}
