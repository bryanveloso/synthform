import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'
import { useRef } from 'react'

import { getEventComponent } from '@/components/shared/timeline/events'
import { Frame, Item } from '@/components/ui/chyron'
import { Chevron } from '@/components/ui/icons'
import { useTimeline } from '@/hooks/use-timeline'
import { cn } from '@/lib/utils'
import type { TimelineEvent } from '@/types/events'

import { ChatNotification, Cheer, Follow } from './item'

export const Timeline = () => {
  const { events: timelineEvents } = useTimeline(20)

  const eventRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const animatedEvents = useRef<Set<string>>(new Set())


  useGSAP(() => {
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
      gsap.set(element, { display: 'block', opacity: 0, y: 64 })

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
              duration: 0.5,
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
          duration: 1,
          delay: index * 0.05,
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

  return (
    <Frame>
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
                if (el) eventRefs.current.set(event.id, el)
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
