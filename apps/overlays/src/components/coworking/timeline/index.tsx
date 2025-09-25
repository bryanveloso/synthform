import { useEffect, useRef, useState, useCallback } from 'react'
import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'
import { useTimeline } from '@/hooks/use-timeline'
import { useRealtimeStore } from '@/store/realtime'
import { cn } from '@/lib/utils'
import { getEventComponent } from '@/components/shared/timeline/events'
import {
  ChatNotification,
  Cheer,
  Follow,
  RedemptionAdd,
} from './item'

interface TimelineProps {
  autoHideDelay?: number // ms before auto-hiding (default: 30000)
  showOnNewEvents?: boolean // whether to show when new events arrive (default: true)
}

export const Timeline = ({ autoHideDelay = 30000, showOnNewEvents = true }: TimelineProps = {}) => {
  const { events: timelineEvents, isStale } = useTimeline(15)
  const lastPushTime = useRealtimeStore((state) => state.timeline.lastPushTime)
  const [isVisible, setIsVisible] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const eventRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const animatedEvents = useRef<Set<string>>(new Set())
  const hideTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined)

  // Auto-hide management
  const startHideTimer = useCallback(() => {
    // Clear existing timer
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current)
    }

    // Set new timer
    hideTimeoutRef.current = setTimeout(() => {
      console.log('Timer expired, hiding timeline')
      setIsVisible(false)
    }, autoHideDelay)
  }, [autoHideDelay])

  // Show timeline when push events arrive
  const prevPushTime = useRef(0)
  useEffect(() => {
    if (!showOnNewEvents) return

    // Only show if lastPushTime actually changed to a new value
    if (lastPushTime > 0 && lastPushTime !== prevPushTime.current) {
      console.log('Showing timeline, starting hide timer')
      setIsVisible(true)
      startHideTimer()
      prevPushTime.current = lastPushTime
    }
  }, [lastPushTime, showOnNewEvents, startHideTimer])

  // TEMPORARY: Test trigger with 'T' key
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 't' || e.key === 'T') {
        console.log('Test trigger: showing timeline')
        setIsVisible(true)
        startHideTimer()
      }
    }
    window.addEventListener('keypress', handleKeyPress)
    return () => window.removeEventListener('keypress', handleKeyPress)
  }, [startHideTimer])

  // Animate visibility changes
  useGSAP(() => {
    if (containerRef.current) {
      if (isVisible) {
        gsap.to(containerRef.current, {
          opacity: 1,
          y: 0,
          duration: 0.5,
          ease: 'power3.out',
        })
      } else {
        gsap.to(containerRef.current, {
          opacity: 0,
          y: 48,
          duration: 0.3,
          ease: 'power2.in',
        })
      }
    }
  }, [isVisible])

  // Cleanup refs and timers on unmount
  useEffect(() => {
    const refs = eventRefs.current
    const animated = animatedEvents.current
    return () => {
      refs.clear()
      animated.clear()
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current)
      }
    }
  }, [])

  // Animate new events appearing
  useGSAP(() => {
    const elementsToAnimate: { element: HTMLElement; event: TimelineEvent }[] = []

    timelineEvents.forEach((event) => {
      const element = eventRefs.current.get(event.id)

      // Only animate if this event hasn't been animated yet
      if (element && !animatedEvents.current.has(event.id)) {
        elementsToAnimate.push({ element, event })
        animatedEvents.current.add(event.id)
      }
    })

    // Batch animate all new elements with stagger
    if (elementsToAnimate.length > 0) {
      elementsToAnimate.forEach(({ element, event }, index) => {
        const targetOpacity = isStale(event) ? 0.4 : 1
        gsap.fromTo(
          element,
          { x: -50, opacity: 0, scale: 0.95 },
          {
            x: 0,
            opacity: targetOpacity,
            scale: 1,
            duration: 0.5,
            ease: 'power3.out',
            delay: index * 0.05,
          },
        )
      })
    }

    // Clean up refs for removed events
    const currentEventIds = new Set(timelineEvents.map((event) => event.id))
    animatedEvents.current.forEach((id) => {
      if (!currentEventIds.has(id)) {
        eventRefs.current.delete(id)
        animatedEvents.current.delete(id)
      }
    })
  }, [timelineEvents])

  return (
    <div
      ref={containerRef}
      className={cn(
        'bg-shark-960 relative overflow-x-hidden transition-opacity',
        !isVisible && 'pointer-events-none',
      )}
      style={{ opacity: 0, transform: 'translateY(48px)' }}
      data-timeline>
      <div className="to-shark-960 absolute right-0 z-10 h-full w-48 bg-gradient-to-r from-transparent"></div>
      <div className="flex items-center gap-2 pl-6">
        <div className="from-shark-880 to-shark-920 rounded-sm bg-gradient-to-b p-2 inset-ring-1 inset-ring-white/5 outline-1">
          <svg
            version="1.1"
            id="Arrow-Right-1--Streamline-Streamline-3.0"
            xmlns="http://www.w3.org/2000/svg"
            xmlnsXlink="http://www.w3.org/1999/xlink"
            x="0"
            y="0"
            viewBox="0 0 24 24"
            xmlSpace="preserve"
            enableBackground="new 0 0 24 24"
            className="text-lime size-3">
            <path
              d="M19.5 12c0 0.7 -0.3 1.3 -0.8 1.7L7.5 23.6c-0.8 0.7 -2 0.6 -2.6 -0.2 -0.6 -0.8 -0.6 -1.9 0.2 -2.6l9.8 -8.6c0.1 -0.1 0.1 -0.2 0 -0.4L5.1 3.2c-0.8 -0.7 -0.8 -1.9 -0.1 -2.6 0.7 -0.7 1.8 -0.8 2.6 -0.2l11.2 9.8c0.4 0.5 0.7 1.1 0.7 1.8z"
              fill="currentColor"
              strokeWidth="1"></path>
          </svg>
        </div>
        {timelineEvents.map((event) => {
          const component = getEventComponent(event, {
            ChatNotification,
            Cheer,
            Follow,
            RedemptionAdd,
          })
          if (!component) return null

          return (
            <div
              key={event.id}
              ref={(el) => {
                if (el) eventRefs.current.set(event.id, el)
              }}
              className={cn(
                `font-sans text-sm text-white`,
                isStale(event) ? 'opacity-50' : 'opacity-100',
              )}>
              {component}
            </div>
          )
        })}
      </div>
    </div>
  )
}
