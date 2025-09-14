import { useEffect, useRef } from 'react'
import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'
import { useTimeline } from '@/hooks/use-timeline'
import { cn } from '@/lib/utils'
import type { TimelineEvent } from '@/types/events'

import { Cheer, Follow, Subscription, SubscriptionGift, SubscriptionMessage, RedemptionAdd, Raid } from './item'

const getType = (event: TimelineEvent) => {
  switch (event.type) {
    case 'twitch.channel.follow':
      return <Follow event={event} />
    case 'twitch.channel.subscribe':
      return <Subscription event={event} />
    case 'twitch.channel.subscription.gift':
      return <SubscriptionGift event={event} />
    case 'twitch.channel.subscription.message':
      return <SubscriptionMessage event={event} />
    case 'twitch.channel.cheer':
      return <Cheer event={event} />
    case 'twitch.channel.channel_points_custom_reward_redemption.add':
      return <RedemptionAdd event={event} />
    case 'twitch.channel.raid':
      return <Raid event={event} />
    default:
      return null
  }
}

export const Timeline = () => {
  const { events: timelineEvents, isStale } = useTimeline(15)
  const containerRef = useRef<HTMLDivElement>(null)
  const eventRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const animatedEvents = useRef<Set<string>>(new Set())

  // Cleanup refs on unmount
  useEffect(() => {
    return () => {
      eventRefs.current.clear()
      animatedEvents.current.clear()
    }
  }, [])

  // Animate new events as they appear
  useGSAP(() => {
    const elementsToAnimate: HTMLElement[] = []

    timelineEvents.forEach((event) => {
      const element = eventRefs.current.get(event.id)

      // Only animate if this event hasn't been animated yet
      if (element && !animatedEvents.current.has(event.id)) {
        elementsToAnimate.push(element)
        animatedEvents.current.add(event.id)
      }
    })

    // Batch animate all new elements with stagger
    if (elementsToAnimate.length > 0) {
      gsap.fromTo(elementsToAnimate,
        { x: -50, opacity: 0, scale: 0.95 },
        { x: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'power3.out', stagger: 0.05 }
      )
    }

    // Clean up refs for removed events
    const currentEventIds = new Set(timelineEvents.map(e => e.id))
    animatedEvents.current.forEach(id => {
      if (!currentEventIds.has(id)) {
        eventRefs.current.delete(id)
        animatedEvents.current.delete(id)
      }
    })
  }, [timelineEvents])

  return (
    <div ref={containerRef} className="relative overflow-x-hidden" data-timeline>
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
          const component = getType(event)
          if (!component) return null

          return (
            <div
              key={event.id}
              ref={(el) => {
                if (el) eventRefs.current.set(event.id, el)
              }}
              className={cn(`font-sans text-sm text-white`, isStale(event) ? 'opacity-50' : 'opacity-100')}
              style={{ opacity: 0 }} // Start invisible for animation
            >
              {component}
            </div>
          )
        })}
      </div>
    </div>
  )
}
