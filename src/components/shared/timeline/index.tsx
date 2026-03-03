import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'
import { useRef, useEffect } from 'react'

import { getEventComponent } from '@/components/shared/timeline/events'
import { Frame, Item } from '@/components/ui/chyron'
import { Chevron } from '@/components/ui/icons'
import { useTimeline } from '@/hooks/use-timeline'
import { usePipelineTest } from '@/hooks/use-pipeline-test'
import { cn } from '@/lib/utils'
import type { TimelineEvent } from '@/types/events'
import {
  TIMELINE_AUTO_HIDE_DELAY,
  TIMELINE_MAX_EVENTS,
  TIMELINE_SHOW_DURATION,
  TIMELINE_HIDE_DURATION,
  TIMELINE_ITEM_FADE_DURATION,
  TIMELINE_ITEM_CASCADE_DELAY,
  TIMELINE_NEW_ITEM_DURATION,
  TIMELINE_SLIDE_DURATION,
  TIMELINE_HIDDEN_Y,
  TIMELINE_ITEM_INITIAL_Y,
} from '@/config/timeline'

import { ChatNotification, Cheer, Follow } from './item'

export const Timeline = () => {
  const { events: timelineEvents, lastPushTime } = useTimeline(TIMELINE_MAX_EVENTS)

  // Enable pipeline testing with keypress (dev only)
  usePipelineTest()

  const eventRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const animatedEvents = useRef<Set<string>>(new Set())
  const containerRef = useRef<HTMLDivElement>(null)
  const hideTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined)
  const isVisible = useRef(false)


  // Show/hide timeline based on lastPushTime
  useGSAP(() => {
    if (containerRef.current) {
      if (lastPushTime > 0 && timelineEvents.length > 0) {
        // Show timeline
        if (!isVisible.current) {
          isVisible.current = true

          // First, hide all current items to prevent flash
          const items = Array.from(eventRefs.current.values())
          items.forEach(item => {
            gsap.set(item, { opacity: 0, y: TIMELINE_ITEM_INITIAL_Y })
          })

          // Animate container appearing
          gsap.to(containerRef.current, {
            y: 0,
            duration: TIMELINE_SHOW_DURATION,
            ease: 'power3.out',
            onComplete: () => {
              // After container is visible, cascade in existing items
              items.forEach((item, index) => {
                gsap.to(item, {
                  opacity: 1,
                  y: 0,
                  duration: TIMELINE_ITEM_FADE_DURATION,
                  delay: index * TIMELINE_ITEM_CASCADE_DELAY,
                  ease: 'power2.out',
                })
              })
            }
          })
        }

        // Reset hide timer
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current)
        }
        hideTimeoutRef.current = setTimeout(() => {
          isVisible.current = false
          if (containerRef.current) {
            gsap.to(containerRef.current, {
              y: TIMELINE_HIDDEN_Y,
              duration: TIMELINE_HIDE_DURATION,
              ease: 'power2.in',
              onComplete: () => {
                // Clear animated events when timeline is fully hidden
                // So next time it shows, all items cascade in together
                animatedEvents.current.clear()
              }
            })
          }
        }, TIMELINE_AUTO_HIDE_DELAY)
      }
    }
  }, [lastPushTime, timelineEvents.length])

  useGSAP(() => {
    // Only handle new items when timeline is already visible
    if (!isVisible.current) return

    const newElements: { element: HTMLElement; event: TimelineEvent }[] = []
    const existingElements: HTMLElement[] = []

    timelineEvents.forEach((event) => {
      const element = eventRefs.current.get(event.id)
      if (element) {
        if (!animatedEvents.current.has(event.id)) {
          newElements.push({ element, event })
          animatedEvents.current.add(event.id)
        } else {
          // Reset any previous transforms on existing elements
          gsap.set(element, { x: 0 })
          existingElements.push(element!)
        }
      }
    })

    if (newElements.length === 0) return

    const timeline = gsap.timeline()

    // For the slide effect, we need to handle flex reflow
    newElements.forEach(({ element }, index) => {
      // Hide new element initially (no reflow yet)
      gsap.set(element, { display: 'none' })

      // Capture current positions of existing elements
      const oldPositions = existingElements.map((el) => el.getBoundingClientRect().left)

      // Show new element (causes reflow) but keep it invisible
      gsap.set(element, { display: 'block', opacity: 0, y: TIMELINE_HIDDEN_Y })

      // Capture new positions after reflow
      const newPositions = existingElements.map((el) => el.getBoundingClientRect().left)

      // Calculate how much each element moved due to reflow
      existingElements.forEach((el, i) => {
        const shift = newPositions[i] - oldPositions[i]
        if (shift !== 0) {
          // Put element back to old position
          gsap.set(el, { x: -shift })
          // Animate to new position
          timeline.to(
            el,
            {
              x: 0,
              duration: TIMELINE_SLIDE_DURATION,
              ease: 'power3.out',
            },
            0,
          )
        }
      })

      // Animate new element appearing
      timeline.to(
        element,
        {
          y: 0,
          opacity: 1,
          duration: TIMELINE_NEW_ITEM_DURATION,
          delay: index * TIMELINE_ITEM_CASCADE_DELAY,
          ease: 'power3.out',
        },
        0,
      )
    })

    const currentEventIds = new Set(timelineEvents.map((e) => e.id))
    animatedEvents.current.forEach((id) => {
      if (!currentEventIds.has(id)) {
        animatedEvents.current.delete(id)
        eventRefs.current.delete(id)
      }
    })
  }, [timelineEvents])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current)
      }
    }
  }, [])

  return (
    <Frame ref={containerRef} style={{ transform: `translateY(${TIMELINE_HIDDEN_Y}px)` }}>
      <div className="flex h-full items-center gap-8 p-6">
        <div className="from-shark-840 to-shark-880 inset-ring-shark-800 flex size-8 items-center justify-center rounded-sm bg-gradient-to-b inset-ring-1">
          <Chevron />
        </div>

        {timelineEvents.map((event, i) => {
          const component = getEventComponent(event, {
            ChatNotification,
            Cheer,
            Follow,
          })
          if (!component) return null

          return (
            <Item
              key={event.id}
              ref={(el) => {
                if (el) {
                  eventRefs.current.set(event.id, el)
                } else {
                  // Clean up ref when component unmounts
                  eventRefs.current.delete(event.id)
                }
              }}
              className={cn('', { '-ml-4': i === 0 })}>
              {component}
            </Item>
          )
        })}
      </div>
    </Frame>
  )
}
