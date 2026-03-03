import { useEffect, useCallback } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import { TestEventFactory } from '@/lib/test/events'
import type { TimelineEvent, ChatNotificationEvent } from '@/types/events'
import { ALERT_PROCESS_DELAY, TEST_EVENT_STAGGER_DELAY } from '@/config/timeline'

/**
 * Hook for testing the entire event pipeline with keypress triggers.
 * Press 'P' for single event, 'Shift+P' for multiple events, 'O' for timeline-only.
 */
export function usePipelineTest() {
  const addAlert = useRealtimeStore((state) => state.addAlert)
  const updateMessage = useRealtimeStore((state) => state.updateMessage)

  // Trigger a single random test event
  const triggerSingleEvent = useCallback(() => {
    const { alert, timeline } = TestEventFactory.random()

    const noticeType = timeline.type === 'twitch.channel.chat.notification'
      ? (timeline as ChatNotificationEvent).data.payload.notice_type
      : undefined

    console.log('🧪 Single Event Test:', {
      alertType: alert.type,
      timelineType: timeline.type,
      noticeType,
    })

    // Add alert first (will be processed)
    addAlert(alert)

    // Need a small delay for alert to move from queue to currentAlert
    // Otherwise hasAlertWithId won't find it
    setTimeout(() => {
      updateMessage('timeline:push', timeline)
    }, ALERT_PROCESS_DELAY)
  }, [addAlert, updateMessage])

  // Trigger multiple test events
  const triggerMultipleEvents = useCallback(() => {
    const events = [
      TestEventFactory.follow(),
      TestEventFactory.sub(undefined, 'Tier 1'),
      TestEventFactory.cheer(undefined, 500),
      TestEventFactory.resub(undefined, 12, 'Tier 2'),
      TestEventFactory.raid(undefined, 25),
      TestEventFactory.communityGift(undefined, 5, 'Tier 1'),
    ]

    events.forEach(({ alert, timeline }, index) => {
      setTimeout(() => {
        const noticeType = timeline.type === 'twitch.channel.chat.notification'
          ? (timeline as ChatNotificationEvent).data.payload.notice_type
          : undefined

        console.log(`📤 Event ${index + 1}/${events.length}:`, {
          alertType: alert.type,
          timelineType: timeline.type,
          noticeType,
        })

        // Add alert first
        addAlert(alert)
        // Small delay for alert to process before timeline event
        setTimeout(() => {
          updateMessage('timeline:push', timeline)
        }, ALERT_PROCESS_DELAY)
      }, index * TEST_EVENT_STAGGER_DELAY) // Stagger events to allow natural completion
    })
  }, [addAlert, updateMessage])

  // Trigger timeline-only event (no alert orchestration)
  const triggerTimelineOnly = useCallback(() => {
    console.log('🧪 Pipeline Test: Triggering timeline-only event')

    const timelineEvent: TimelineEvent = {
      id: `timeline-only-${Date.now()}`,
      type: 'twitch.channel.channel_points_custom_reward_redemption.add',
      data: {
        timestamp: new Date().toISOString(),
        user_name: 'TimelineTestUser',
        payload: {
          id: 'redemption-123',
          user_id: 'test-user-timeline',
          user_name: 'TimelineTestUser',
          user_display_name: 'TimelineTestUser',
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          broadcaster_user_display_name: 'Broadcaster',
          user_input: null,
          status: 'fulfilled',
          reward: {
            id: 'reward-456',
            title: 'Test Redemption',
            cost: 500,
            prompt: 'Test reward prompt',
          },
          redeemed_at: new Date().toISOString(),
        },
      },
    }

    console.log('📤 Sending timeline-only event:', timelineEvent)
    updateMessage('timeline:push', timelineEvent)
  }, [updateMessage])

  // Set up keypress listener
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      switch (e.key) {
        case 'p':
        case 'P':
          e.preventDefault()
          if (e.shiftKey) {
            triggerMultipleEvents()
          } else {
            triggerSingleEvent()
          }
          break
        case 'o':
        case 'O':
          e.preventDefault()
          triggerTimelineOnly()
          break
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [triggerSingleEvent, triggerMultipleEvents, triggerTimelineOnly])

  return {
    triggerSingleEvent,
    triggerMultipleEvents,
    triggerTimelineOnly,
  }
}