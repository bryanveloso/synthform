"""TwitchEventHandler - Business logic for processing Twitch events."""

from __future__ import annotations

import json
import logging
import os

# Setup Django for standalone execution
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")

import django

django.setup()

import redis.asyncio as redis  # noqa: E402
from asgiref.sync import sync_to_async  # noqa: E402
from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402

from events.models import Event  # noqa: E402
from events.models import Member  # noqa: E402

logger = logging.getLogger(__name__)


class TwitchEventHandler:
    """Handles business logic for Twitch events without TwitchIO client dependency."""

    def __init__(self):
        """Initialize the event handler."""
        self._redis_client = redis.Redis.from_url(
            settings.REDIS_URL or "redis://redis:6379/0"
        )

        # Type-specific event handler mapping
        self.EVENT_HANDLERS = None
        self._setup_event_handlers()

        logger.info("TwitchEventHandler initialized")

    def _setup_event_handlers(self):
        """Setup type-specific event handlers for different TwitchIO payload classes."""
        # Import TwitchIO models for type mapping
        from twitchio.models import eventsub_

        # Map TwitchIO payload classes to their specific handlers
        self.EVENT_HANDLERS = {
            # Chat events
            eventsub_.ChatMessage: self._handle_chat_message,
            eventsub_.ChatNotification: self._handle_chat_notification,
            eventsub_.ChatMessageDelete: self._handle_chat_message_delete,
            eventsub_.ChannelChatClear: self._handle_chat_clear,
            eventsub_.ChannelChatClearUserMessages: self._handle_chat_clear_user,
            # Channel events
            eventsub_.ChannelFollow: self._handle_channel_follow,
            eventsub_.ChannelUpdate: self._handle_channel_update,
            eventsub_.ChannelCheer: self._handle_channel_cheer,
            eventsub_.ChannelRaid: self._handle_channel_raid,
            eventsub_.ChannelBan: self._handle_channel_ban,
            eventsub_.ChannelUnban: self._handle_channel_unban,
            # Subscription events
            eventsub_.ChannelSubscribe: self._handle_channel_subscribe,
            eventsub_.ChannelSubscriptionEnd: self._handle_channel_subscription_end,
            eventsub_.ChannelSubscriptionGift: self._handle_channel_subscription_gift,
            eventsub_.ChannelSubscriptionMessage: self._handle_channel_subscription_message,
            # Stream events
            eventsub_.StreamOnline: self._handle_stream_online,
            eventsub_.StreamOffline: self._handle_stream_offline,
            # Channel Points events
            eventsub_.ChannelPointsRewardAdd: self._handle_custom_reward_add,
            eventsub_.ChannelPointsRewardUpdate: self._handle_custom_reward_update,
            eventsub_.ChannelPointsRewardRemove: self._handle_custom_reward_remove,
            eventsub_.ChannelPointsRedemptionAdd: self._handle_custom_redemption_add,
            eventsub_.ChannelPointsRedemptionUpdate: self._handle_custom_redemption_update,
            # Poll events
            eventsub_.ChannelPollBegin: self._handle_poll_begin,
            eventsub_.ChannelPollProgress: self._handle_poll_progress,
            eventsub_.ChannelPollEnd: self._handle_poll_end,
            # Prediction events
            eventsub_.ChannelPredictionBegin: self._handle_prediction_begin,
            eventsub_.ChannelPredictionProgress: self._handle_prediction_progress,
            eventsub_.ChannelPredictionLock: self._handle_prediction_lock,
            eventsub_.ChannelPredictionEnd: self._handle_prediction_end,
            # Hype Train events
            eventsub_.HypeTrainBegin: self._handle_hype_train_begin,
            eventsub_.HypeTrainProgress: self._handle_hype_train_progress,
            eventsub_.HypeTrainEnd: self._handle_hype_train_end,
            # Goal events
            eventsub_.GoalBegin: self._handle_goal_begin,
            eventsub_.GoalProgress: self._handle_goal_progress,
            eventsub_.GoalEnd: self._handle_goal_end,
            # Ad break events
            eventsub_.ChannelAdBreakBegin: self._handle_ad_break_begin,
            # VIP events
            eventsub_.ChannelVIPAdd: self._handle_vip_add,
            eventsub_.ChannelVIPRemove: self._handle_vip_remove,
            # Shoutout events
            eventsub_.ShoutoutCreate: self._handle_shoutout_create,
        }

    async def event_follow(self, payload):
        """Handle channel follow events."""
        await self._create_event_from_payload("channel.follow", payload)

    async def event_subscription(self, payload):
        """Handle channel subscription events."""
        await self._create_event_from_payload("channel.subscribe", payload)

    async def event_subscription_gift(self, payload):
        """Handle channel subscription gift events."""
        await self._create_event_from_payload("channel.subscription.gift", payload)

    async def event_cheer(self, payload):
        """Handle channel cheer events."""
        await self._create_event_from_payload("channel.cheer", payload)

    async def event_raid(self, payload):
        """Handle channel raid events."""
        await self._create_event_from_payload("channel.raid", payload)

    async def event_ban(self, payload):
        """Handle channel ban events."""
        await self._create_event_from_payload("channel.ban", payload)

    async def event_unban(self, payload):
        """Handle channel unban events."""
        await self._create_event_from_payload("channel.unban", payload)

    async def event_stream_online(self, payload):
        """Handle stream online events."""
        await self._create_event_from_payload("stream.online", payload)

        # Session management: Start or continue session
        from audio.session_manager import cancel_session_timeout
        from audio.session_manager import get_or_create_active_session

        try:
            session = await get_or_create_active_session()
            await cancel_session_timeout(session)
            logger.info(f"Stream online: Session {session.id} active, timeout canceled")
        except Exception as e:
            logger.error(f"Error managing session on stream online: {e}")

    async def event_stream_offline(self, payload):
        """Handle stream offline events."""
        await self._create_event_from_payload("stream.offline", payload)

        # Session management: Start timeout countdown
        from audio.session_manager import get_or_create_active_session
        from audio.session_manager import start_session_timeout

        try:
            session = await get_or_create_active_session()
            await start_session_timeout(session)
            logger.info(f"Stream offline: Started timeout for session {session.id}")
        except Exception as e:
            logger.error(f"Error managing session on stream offline: {e}")

    async def event_channel_update(self, payload):
        """Handle channel update events."""
        await self._create_event_from_payload("channel.update", payload)

    # Additional subscription events
    async def event_subscription_end(self, payload):
        """Handle channel subscription end events."""
        await self._create_event_from_payload("channel.subscription.end", payload)

    async def event_subscription_message(self, payload):
        """Handle channel subscription message events."""
        await self._create_event_from_payload("channel.subscription.message", payload)

    # Chat events
    async def event_chat_clear(self, payload):
        """Handle chat clear events."""
        await self._create_event_from_payload("channel.chat.clear", payload)

    async def event_chat_clear_user(self, payload):
        """Handle chat clear user messages events."""
        await self._create_event_from_payload(
            "channel.chat.clear_user_messages", payload
        )

    async def event_message(self, payload):
        """Handle chat message events."""
        await self._create_event_from_payload("channel.chat.message", payload)

    async def event_message_delete(self, payload):
        """Handle chat message delete events."""
        await self._create_event_from_payload("channel.chat.message.delete", payload)

    async def event_chat_notification(self, payload):
        """Handle chat notification events."""
        await self._create_event_from_payload("channel.chat.notification", payload)

    # Channel Points events
    async def event_custom_reward_add(self, payload):
        """Handle channel points reward add events."""
        await self._create_event_from_payload(
            "channel.channel_points_custom_reward.add", payload
        )

    async def event_custom_reward_update(self, payload):
        """Handle channel points reward update events."""
        await self._create_event_from_payload(
            "channel.channel_points_custom_reward.update", payload
        )

    async def event_custom_reward_remove(self, payload):
        """Handle channel points reward remove events."""
        await self._create_event_from_payload(
            "channel.channel_points_custom_reward.remove", payload
        )

    async def event_custom_redemption_add(self, payload):
        """Handle channel points redemption add events."""
        await self._create_event_from_payload(
            "channel.channel_points_custom_reward_redemption.add", payload
        )
        # Check if this is a limit break reward redemption
        await self._handle_limit_break_update(payload)

    async def event_custom_redemption_update(self, payload):
        """Handle channel points redemption update events."""
        await self._create_event_from_payload(
            "channel.channel_points_custom_reward_redemption.update", payload
        )
        # Check if this is a limit break reward redemption
        await self._handle_limit_break_update(payload)

    async def event_automatic_redemption_add(self, payload):
        """Handle automatic redemption add events."""
        await self._create_event_from_payload(
            "channel.channel_points_automatic_reward_redemption.add", payload
        )

    # Poll events
    async def event_poll_begin(self, payload):
        """Handle poll begin events."""
        await self._create_event_from_payload("channel.poll.begin", payload)

    async def event_poll_progress(self, payload):
        """Handle poll progress events."""
        await self._create_event_from_payload("channel.poll.progress", payload)

    async def event_poll_end(self, payload):
        """Handle poll end events."""
        await self._create_event_from_payload("channel.poll.end", payload)

    # Prediction events
    async def event_prediction_begin(self, payload):
        """Handle prediction begin events."""
        await self._create_event_from_payload("channel.prediction.begin", payload)

    async def event_prediction_progress(self, payload):
        """Handle prediction progress events."""
        await self._create_event_from_payload("channel.prediction.progress", payload)

    async def event_prediction_lock(self, payload):
        """Handle prediction lock events."""
        await self._create_event_from_payload("channel.prediction.lock", payload)

    async def event_prediction_end(self, payload):
        """Handle prediction end events."""
        await self._create_event_from_payload("channel.prediction.end", payload)

    # Ad break events
    async def handle_ad_break(self, payload):
        """Handle ad break events from TwitchIO."""
        await self._create_event_from_payload("channel.ad_break.begin", payload)

    # Charity events
    async def event_charity_campaign_donate(self, payload):
        """Handle charity campaign donation events."""
        await self._create_event_from_payload(
            "channel.charity_campaign.donate", payload
        )

    # Hype Train events
    async def event_hype_train(self, payload):
        """Handle hype train begin events."""
        await self._create_event_from_payload("channel.hype_train.begin", payload)

    async def event_hype_train_progress(self, payload):
        """Handle hype train progress events."""
        await self._create_event_from_payload("channel.hype_train.progress", payload)

    async def event_hype_train_end(self, payload):
        """Handle hype train end events."""
        await self._create_event_from_payload("channel.hype_train.end", payload)

    # Goal events
    async def event_goal_begin(self, payload):
        """Handle goal begin events."""
        await self._create_event_from_payload("channel.goal.begin", payload)

    async def event_goal_progress(self, payload):
        """Handle goal progress events."""
        await self._create_event_from_payload("channel.goal.progress", payload)

    async def event_goal_end(self, payload):
        """Handle goal end events."""
        await self._create_event_from_payload("channel.goal.end", payload)

    # Shoutout events
    async def event_shoutout_create(self, payload):
        """Handle shoutout create events."""
        await self._create_event_from_payload("channel.shoutout.create", payload)

    # VIP events
    async def event_vip_add(self, payload):
        """Handle VIP add events."""
        await self._create_event_from_payload("channel.vip.add", payload)

    async def event_vip_remove(self, payload):
        """Handle VIP remove events."""
        await self._create_event_from_payload("channel.vip.remove", payload)

    # Ad break events
    async def event_ad_break(self, payload):
        """Handle ad break events."""
        await self._create_event_from_payload("channel.ad_break.begin", payload)

    async def _create_event_from_payload(self, event_type: str, payload):
        """Dispatcher - route to type-specific handler based on payload class."""
        try:
            payload_class = type(payload)
            logger.info(
                f"Processing {event_type} with payload class: {payload_class.__name__}"
            )

            # Find the appropriate handler for this payload type
            handler = self.EVENT_HANDLERS.get(payload_class)
            if handler:
                logger.info(
                    f"Found handler for {payload_class.__name__}: {handler.__name__}"
                )
                return await handler(event_type, payload)
            else:
                # Log available handlers for debugging
                available_handlers = list(self.EVENT_HANDLERS.keys())
                logger.error(
                    f"No handler found for payload type: {payload_class.__name__}"
                )
                logger.error(
                    f"Available handlers: {[cls.__name__ for cls in available_handlers]}"
                )

                # Fallback to generic extraction as last resort
                logger.warning(
                    f"Using fallback generic extraction for {payload_class.__name__}"
                )
                return await self._handle_unknown_payload(event_type, payload)

        except Exception as e:
            logger.error(f"Error in dispatcher for {event_type}: {e}")

    # Type-specific payload handlers (these will be filled in from the original file)
    # Due to the length, I'm including a representative sample. The full implementation
    # would include all the handler methods from the original file.

    async def _handle_chat_message(self, event_type: str, payload):
        """Handle ChatMessage payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "text": payload.text,
            "type": payload.type,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "user_id": payload.chatter.id if payload.chatter else None,
            "user_name": payload.chatter.name if payload.chatter else None,
            "user_display_name": payload.chatter.display_name
            if payload.chatter
            else None,
            "colour": str(payload.colour) if payload.colour else None,
            "badges": [
                {"set_id": badge.set_id, "id": badge.id, "info": badge.info}
                for badge in payload.badges
            ]
            if payload.badges
            else [],
            "fragments": [
                {
                    "type": fragment.type,
                    "text": fragment.text,
                    "cheermote": {
                        "prefix": fragment.cheermote.prefix,
                        "bits": fragment.cheermote.bits,
                        "tier": fragment.cheermote.tier,
                    }
                    if hasattr(fragment, "cheermote") and fragment.cheermote
                    else None,
                    "emote": {
                        "id": fragment.emote.id,
                        "set_id": fragment.emote.set_id,
                        "format": fragment.emote.format,
                    }
                    if hasattr(fragment, "emote") and fragment.emote
                    else None,
                    "mention": {
                        "user_id": fragment.mention.id,
                        "user_name": fragment.mention.name,
                        "user_login": fragment.mention.name,
                    }
                    if hasattr(fragment, "mention") and fragment.mention
                    else None,
                }
                for fragment in payload.fragments
            ],
            "reply": {
                "parent_message_id": payload.reply.parent_message_id,
                "parent_message_body": payload.reply.parent_message_body,
                "parent_user_id": payload.reply.parent_user_id,
                "parent_user_name": payload.reply.parent_user_name,
                "parent_user_login": payload.reply.parent_user_login,
                "thread_message_id": payload.reply.thread_message_id,
                "thread_user_id": payload.reply.thread_user_id,
                "thread_user_name": payload.reply.thread_user_name,
                "thread_user_login": payload.reply.thread_user_login,
            }
            if payload.reply
            else None,
            "cheer": {
                "bits": payload.cheer.bits,
            }
            if payload.cheer
            else None,
            "subscriber": getattr(payload.chatter, "subscriber", False)
            if payload.chatter
            else False,
            "moderator": getattr(payload.chatter, "moderator", False)
            if payload.chatter
            else False,
            "broadcaster": getattr(payload.chatter, "broadcaster", False)
            if payload.chatter
            else False,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChatMessage: {payload.text[:50]}... from {payload.chatter.display_name if payload.chatter else 'Unknown'}"
        )

    async def _handle_channel_follow(self, event_type: str, payload):
        """Handle ChannelFollow payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "user_display_name": payload.user.display_name if payload.user else None,
            "followed_at": payload.followed_at.isoformat()
            if payload.followed_at
            else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "timestamp": payload.timestamp.isoformat() if payload.timestamp else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelFollow: {payload.user.display_name or payload.user.name} followed"
        )

    async def _handle_channel_cheer(self, event_type: str, payload):
        """Handle ChannelCheer payload with its specific structure."""
        payload_dict = {
            "bits": payload.bits,
            "message": payload.message,
            "is_anonymous": payload.is_anonymous,
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelCheer: {payload.bits} bits from {payload.user.name if payload.user else 'Anonymous'}"
        )

    async def _handle_channel_subscribe(self, event_type: str, payload):
        """Handle ChannelSubscribe payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "tier": payload.tier,
            "is_gift": payload.is_gift,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelSubscribe: {payload.user_name} subscribed (tier {payload.tier})"
        )

    async def _handle_channel_raid(self, event_type: str, payload):
        """Handle ChannelRaid payload with its specific structure."""
        payload_dict = {
            "from_broadcaster_user_id": payload.from_broadcaster.id,
            "from_broadcaster_user_name": payload.from_broadcaster.name,
            "to_broadcaster_user_id": payload.to_broadcaster.id,
            "to_broadcaster_user_name": payload.to_broadcaster.name,
            "viewers": payload.viewers,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelRaid: {payload.from_broadcaster.name} raided with {payload.viewers} viewers"
        )

    async def _handle_stream_online(self, event_type: str, payload):
        """Handle StreamOnline payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "type": payload.type,
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "game_id": getattr(payload, "game_id", None),
            "game_name": getattr(payload, "game_name", None),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(f"Processed StreamOnline: {payload.broadcaster.name} went live")

    async def _handle_stream_offline(self, event_type: str, payload):
        """Handle StreamOffline payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(f"Processed StreamOffline: {payload.broadcaster.name} went offline")

    async def _handle_unknown_payload(self, event_type: str, payload):
        """Fallback handler for unknown payload types."""
        logger.warning(
            f"Using fallback handler for unknown payload type: {type(payload).__name__}"
        )

        # Extract basic attributes as fallback
        payload_dict = {}
        for attr_name in dir(payload):
            if attr_name.startswith("_") or callable(getattr(payload, attr_name, None)):
                continue
            try:
                value = getattr(payload, attr_name)
                if value is not None and isinstance(value, str | int | float | bool):
                    payload_dict[attr_name] = value
                elif hasattr(value, "isoformat"):  # datetime
                    payload_dict[attr_name] = value.isoformat()
                else:
                    payload_dict[attr_name] = str(value)
            except Exception:
                continue

        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed unknown payload type {type(payload).__name__} with fallback handler"
        )

    # Type-specific event handlers - each knows its payload structure
    async def _handle_chat_notification(self, event_type: str, payload):
        """Handle ChatNotification payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "chatter_user_id": payload.chatter.id if payload.chatter else None,
            "chatter_user_name": payload.chatter.name if payload.chatter else None,
            "chatter_user_login": payload.chatter.name if payload.chatter else None,
            "chatter_display_name": payload.chatter.display_name
            if payload.chatter
            else None,
            "chatter_is_anonymous": getattr(payload, "chatter_is_anonymous", False),
            "color": getattr(payload, "color", None),
            "badges": [
                {
                    "set_id": badge.set_id,
                    "id": badge.id,
                    "info": getattr(badge, "info", None),
                }
                for badge in payload.badges
            ]
            if hasattr(payload, "badges") and payload.badges
            else [],
            "system_message": getattr(payload, "system_message", None),
            "message_id": getattr(payload, "message_id", None),
            "message": {
                "text": payload.message.text,
                "fragments": [
                    {"type": getattr(frag, "type", None), "text": frag.text}
                    for frag in payload.message.fragments
                ]
                if hasattr(payload.message, "fragments") and payload.message.fragments
                else [],
            }
            if hasattr(payload, "message") and payload.message
            else None,
            "notice_type": getattr(payload, "notice_type", None),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChatNotification: {getattr(payload, 'notice_type', 'unknown')} from {payload.chatter.display_name if payload.chatter else 'Anonymous'}"
        )

    async def _handle_chat_message_delete(self, event_type: str, payload):
        """Handle ChatMessageDelete payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "target_user_id": payload.target_user.id,
            "target_user_name": payload.target_user.name,
            "message_id": payload.message_id,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChatMessageDelete: Message from {payload.target_user.name} deleted"
        )

    async def _handle_chat_clear(self, event_type: str, payload):
        """Handle ChannelChatClear payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelChatClear: Chat cleared in {payload.broadcaster.name}'s channel"
        )

    async def _handle_chat_clear_user(self, event_type: str, payload):
        """Handle ChannelChatClearUserMessages payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "target_user_id": payload.target_user.id,
            "target_user_name": payload.target_user.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelChatClearUserMessages: Messages from {payload.target_user.name} cleared"
        )

    async def _handle_channel_update(self, event_type: str, payload):
        """Handle ChannelUpdate payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "language": payload.language,
            "category_id": payload.category_id,
            "category_name": payload.category_name,
            "content_classification_labels": getattr(
                payload, "content_classification_labels", []
            ),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelUpdate: {payload.broadcaster.name} updated channel to '{payload.title}' in {payload.category_name}"
        )

    async def _handle_channel_ban(self, event_type: str, payload):
        """Handle ChannelBan payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "moderator_user_id": payload.moderator.id if payload.moderator else None,
            "moderator_user_name": payload.moderator.name
            if payload.moderator
            else None,
            "reason": payload.reason if hasattr(payload, "reason") else None,
            "banned_at": payload.banned_at.isoformat()
            if hasattr(payload, "banned_at") and payload.banned_at
            else None,
            "ends_at": payload.ends_at.isoformat()
            if hasattr(payload, "ends_at") and payload.ends_at
            else None,
            "is_permanent": payload.is_permanent
            if hasattr(payload, "is_permanent")
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        ban_type = (
            "permanently"
            if payload_dict.get("is_permanent")
            else f"until {payload_dict.get('ends_at')}"
        )
        logger.info(
            f"Processed ChannelBan: {payload_dict.get('user_name')} banned {ban_type} by {payload_dict.get('moderator_user_name')}"
        )

    async def _handle_channel_unban(self, event_type: str, payload):
        """Handle ChannelUnban payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "moderator_user_id": payload.moderator.id if payload.moderator else None,
            "moderator_user_name": payload.moderator.name
            if payload.moderator
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelUnban: {payload_dict.get('user_name')} unbanned by {payload_dict.get('moderator_user_name')}"
        )

    async def _handle_channel_subscription_end(self, event_type: str, payload):
        """Handle ChannelSubscriptionEnd payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "user_login": (await payload.user.user()).name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "tier": payload.tier if hasattr(payload, "tier") else None,
            "is_gift": payload.is_gift if hasattr(payload, "is_gift") else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelSubscriptionEnd: {payload_dict.get('user_name')}'s tier {payload_dict.get('tier')} subscription ended"
        )

    async def _handle_channel_subscription_gift(self, event_type: str, payload):
        """Handle ChannelSubscriptionGift payload with its specific structure."""
        # Get recipient information from subscription_data instead of using gifter as primary user
        recipient = (
            payload.subscription_data.user if payload.subscription_data else None
        )

        payload_dict = {
            # Primary user should be the recipient, not the gifter
            "user_id": recipient.id if recipient else None,
            "user_name": recipient.name if recipient else None,
            "user_login": (await recipient.user()).name if recipient else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "total": payload.total if hasattr(payload, "total") else None,
            "tier": payload.tier if hasattr(payload, "tier") else None,
            "cumulative_total": payload.cumulative_total
            if hasattr(payload, "cumulative_total")
            else None,
            "is_anonymous": payload.is_anonymous
            if hasattr(payload, "is_anonymous")
            else None,
            # Keep gifter information for tracking purposes
            "gifter_id": payload.user.id if payload.user else None,
            "gifter_name": payload.user.name if payload.user else None,
            "gifter_login": (await payload.user.user()).name if payload.user else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        user_name = (
            payload_dict.get("user_name")
            if not payload_dict.get("is_anonymous")
            else "Anonymous"
        )
        logger.info(
            f"Processed ChannelSubscriptionGift: {payload_dict.get('total')} subs from {user_name}"
        )

    async def _handle_channel_subscription_message(self, event_type: str, payload):
        """Handle ChannelSubscriptionMessage payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "user_login": (await payload.user.user()).name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id
            if payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if payload.broadcaster
            else None,
            "tier": payload.tier if hasattr(payload, "tier") else None,
            "message": getattr(payload, "message", None),
            "cumulative_months": payload.cumulative_months
            if hasattr(payload, "cumulative_months")
            else None,
            "streak_months": payload.streak_months
            if hasattr(payload, "streak_months")
            else None,
            "duration_months": payload.duration_months
            if hasattr(payload, "duration_months")
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelSubscriptionMessage: {payload_dict.get('user_name')} resubscribed for {payload_dict.get('cumulative_months')} months"
        )

    async def _handle_custom_reward_add(self, event_type: str, payload):
        """Handle ChannelPointsCustomRewardAdd payload with its specific structure."""
        reward = payload.reward if hasattr(payload, "reward") else payload
        payload_dict = {
            "id": reward.id if hasattr(reward, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "is_enabled": reward.is_enabled if hasattr(reward, "is_enabled") else None,
            "is_paused": reward.is_paused if hasattr(reward, "is_paused") else None,
            "is_in_stock": reward.is_in_stock
            if hasattr(reward, "is_in_stock")
            else None,
            "title": reward.title if hasattr(reward, "title") else None,
            "cost": reward.cost if hasattr(reward, "cost") else None,
            "prompt": reward.prompt if hasattr(reward, "prompt") else None,
            "is_user_input_required": reward.is_user_input_required
            if hasattr(reward, "is_user_input_required")
            else None,
            "should_redemptions_skip_request_queue": reward.should_redemptions_skip_request_queue
            if hasattr(reward, "should_redemptions_skip_request_queue")
            else None,
            "max_per_stream": getattr(reward, "max_per_stream", None),
            "max_per_user_per_stream": getattr(reward, "max_per_user_per_stream", None),
            "background_color": getattr(reward, "background_color", None),
            "image": getattr(reward, "image", None),
            "default_image": getattr(reward, "default_image", None),
            "global_cooldown_seconds": getattr(reward, "global_cooldown_seconds", None),
            "cooldown_expires_at": getattr(reward, "cooldown_expires_at", None),
            "redemptions_redeemed_current_stream": getattr(
                reward, "redemptions_redeemed_current_stream", None
            ),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPointsCustomRewardAdd: '{payload_dict.get('title')}' reward created for {payload_dict.get('cost')} points"
        )

    async def _handle_custom_reward_update(self, event_type: str, payload):
        """Handle ChannelPointsCustomRewardUpdate payload with its specific structure."""
        reward = payload.reward if hasattr(payload, "reward") else payload
        payload_dict = {
            "id": reward.id if hasattr(reward, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "is_enabled": reward.is_enabled if hasattr(reward, "is_enabled") else None,
            "is_paused": reward.is_paused if hasattr(reward, "is_paused") else None,
            "is_in_stock": reward.is_in_stock
            if hasattr(reward, "is_in_stock")
            else None,
            "title": reward.title if hasattr(reward, "title") else None,
            "cost": reward.cost if hasattr(reward, "cost") else None,
            "prompt": reward.prompt if hasattr(reward, "prompt") else None,
            "is_user_input_required": reward.is_user_input_required
            if hasattr(reward, "is_user_input_required")
            else None,
            "should_redemptions_skip_request_queue": reward.should_redemptions_skip_request_queue
            if hasattr(reward, "should_redemptions_skip_request_queue")
            else None,
            "max_per_stream": getattr(reward, "max_per_stream", None),
            "max_per_user_per_stream": getattr(reward, "max_per_user_per_stream", None),
            "background_color": getattr(reward, "background_color", None),
            "image": getattr(reward, "image", None),
            "default_image": getattr(reward, "default_image", None),
            "global_cooldown_seconds": getattr(reward, "global_cooldown_seconds", None),
            "cooldown_expires_at": getattr(reward, "cooldown_expires_at", None),
            "redemptions_redeemed_current_stream": getattr(
                reward, "redemptions_redeemed_current_stream", None
            ),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPointsCustomRewardUpdate: '{payload_dict.get('title')}' reward updated"
        )

    async def _handle_custom_reward_remove(self, event_type: str, payload):
        """Handle ChannelPointsCustomRewardRemove payload with its specific structure."""
        reward = payload.reward if hasattr(payload, "reward") else payload
        payload_dict = {
            "id": reward.id if hasattr(reward, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "is_enabled": reward.is_enabled if hasattr(reward, "is_enabled") else None,
            "is_paused": reward.is_paused if hasattr(reward, "is_paused") else None,
            "is_in_stock": reward.is_in_stock
            if hasattr(reward, "is_in_stock")
            else None,
            "title": reward.title if hasattr(reward, "title") else None,
            "cost": reward.cost if hasattr(reward, "cost") else None,
            "prompt": reward.prompt if hasattr(reward, "prompt") else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPointsCustomRewardRemove: '{payload_dict.get('title')}' reward removed"
        )

    async def _handle_custom_redemption_add(self, event_type: str, payload):
        """Handle ChannelPointsRedemptionAdd payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_input": payload.user_input,
            "status": payload.status,
            "reward": {
                "id": payload.reward.id,
                "title": payload.reward.title,
                "cost": payload.reward.cost,
                "prompt": payload.reward.prompt,
            },
            "redeemed_at": payload.redeemed_at.isoformat()
            if payload.redeemed_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPointsRedemptionAdd: {payload.user.name} redeemed '{payload.reward.title}' for {payload.reward.cost} points"
        )

    async def _handle_custom_redemption_update(self, event_type: str, payload):
        """Handle ChannelPointsRedemptionUpdate payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_input": payload.user_input,
            "status": payload.status,
            "reward": {
                "id": payload.reward.id,
                "title": payload.reward.title,
                "cost": payload.reward.cost,
                "prompt": payload.reward.prompt,
            },
            "redeemed_at": payload.redeemed_at.isoformat()
            if payload.redeemed_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPointsRedemptionUpdate: {payload.user.name}'s redemption of '{payload.reward.title}' updated to {payload.status}"
        )

    async def _handle_poll_begin(self, event_type: str, payload):
        """Handle ChannelPollBegin payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "title": payload.title if hasattr(payload, "title") else None,
            "choices": [
                {
                    "id": choice.id if hasattr(choice, "id") else None,
                    "title": choice.title if hasattr(choice, "title") else None,
                    "votes": choice.votes if hasattr(choice, "votes") else 0,
                    "channel_points_votes": getattr(choice, "channel_points_votes", 0),
                    "bits_votes": getattr(choice, "bits_votes", 0),
                }
                for choice in getattr(payload, "choices", [])
            ],
            "bits_voting_enabled": payload.bits_voting_enabled
            if hasattr(payload, "bits_voting_enabled")
            else None,
            "bits_per_vote": payload.bits_per_vote
            if hasattr(payload, "bits_per_vote")
            else None,
            "channel_points_voting_enabled": payload.channel_points_voting_enabled
            if hasattr(payload, "channel_points_voting_enabled")
            else None,
            "channel_points_per_vote": payload.channel_points_per_vote
            if hasattr(payload, "channel_points_per_vote")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "ends_at": payload.ends_at.isoformat()
            if hasattr(payload, "ends_at") and payload.ends_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        choices_count = len(getattr(payload, "choices", []))
        logger.info(
            f"Processed ChannelPollBegin: '{payload_dict.get('title')}' poll started with {choices_count} choices"
        )

    async def _handle_poll_progress(self, event_type: str, payload):
        """Handle ChannelPollProgress payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "title": payload.title if hasattr(payload, "title") else None,
            "choices": [
                {
                    "id": choice.id if hasattr(choice, "id") else None,
                    "title": choice.title if hasattr(choice, "title") else None,
                    "votes": choice.votes if hasattr(choice, "votes") else 0,
                    "channel_points_votes": getattr(choice, "channel_points_votes", 0),
                    "bits_votes": getattr(choice, "bits_votes", 0),
                }
                for choice in getattr(payload, "choices", [])
            ],
            "bits_voting_enabled": payload.bits_voting_enabled
            if hasattr(payload, "bits_voting_enabled")
            else None,
            "bits_per_vote": payload.bits_per_vote
            if hasattr(payload, "bits_per_vote")
            else None,
            "channel_points_voting_enabled": payload.channel_points_voting_enabled
            if hasattr(payload, "channel_points_voting_enabled")
            else None,
            "channel_points_per_vote": payload.channel_points_per_vote
            if hasattr(payload, "channel_points_per_vote")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "ends_at": payload.ends_at.isoformat()
            if hasattr(payload, "ends_at") and payload.ends_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        choices = getattr(payload, "choices", [])
        total_votes = sum(getattr(choice, "votes", 0) for choice in choices)
        logger.info(
            f"Processed ChannelPollProgress: '{payload_dict.get('title')}' poll progress with {total_votes} total votes"
        )

    async def _handle_poll_end(self, event_type: str, payload):
        """Handle ChannelPollEnd payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "title": payload.title if hasattr(payload, "title") else None,
            "choices": [
                {
                    "id": choice.id if hasattr(choice, "id") else None,
                    "title": choice.title if hasattr(choice, "title") else None,
                    "votes": choice.votes if hasattr(choice, "votes") else 0,
                    "channel_points_votes": getattr(choice, "channel_points_votes", 0),
                    "bits_votes": getattr(choice, "bits_votes", 0),
                }
                for choice in getattr(payload, "choices", [])
            ],
            "bits_voting_enabled": payload.bits_voting_enabled
            if hasattr(payload, "bits_voting_enabled")
            else None,
            "bits_per_vote": payload.bits_per_vote
            if hasattr(payload, "bits_per_vote")
            else None,
            "channel_points_voting_enabled": payload.channel_points_voting_enabled
            if hasattr(payload, "channel_points_voting_enabled")
            else None,
            "channel_points_per_vote": payload.channel_points_per_vote
            if hasattr(payload, "channel_points_per_vote")
            else None,
            "status": payload.status if hasattr(payload, "status") else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "ended_at": payload.ended_at.isoformat()
            if hasattr(payload, "ended_at") and payload.ended_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        choices = getattr(payload, "choices", [])
        winning_choice = (
            max(choices, key=lambda c: getattr(c, "votes", 0)) if choices else None
        )
        winner_info = (
            f" - Winner: '{getattr(winning_choice, 'title', '')}' with {getattr(winning_choice, 'votes', 0)} votes"
            if winning_choice
            else ""
        )
        logger.info(
            f"Processed ChannelPollEnd: '{payload_dict.get('title')}' poll ended with status {payload_dict.get('status')}{winner_info}"
        )

    async def _handle_prediction_begin(self, event_type: str, payload):
        """Handle ChannelPredictionBegin payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.color,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                    "top_predictors": [
                        {
                            "user_id": p.user.id,
                            "user_name": p.user.name,
                            "user_login": (await p.user.user()).name
                            if p.user
                            else None,
                            "channel_points_used": p.channel_points_used,
                            "channel_points_won": p.channel_points_won,
                        }
                        for p in outcome.top_predictors
                    ]
                    if outcome.top_predictors
                    else [],
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "locks_at": payload.locks_at.isoformat() if payload.locks_at else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPredictionBegin: '{payload.title}' prediction started with {len(payload.outcomes)} outcomes"
        )

    async def _handle_prediction_progress(self, event_type: str, payload):
        """Handle ChannelPredictionProgress payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.color,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                    "top_predictors": [
                        {
                            "user_id": p.user.id,
                            "user_name": p.user.name,
                            "user_login": (await p.user.user()).name
                            if p.user
                            else None,
                            "channel_points_used": p.channel_points_used,
                            "channel_points_won": p.channel_points_won,
                        }
                        for p in outcome.top_predictors
                    ]
                    if outcome.top_predictors
                    else [],
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "locks_at": payload.locks_at.isoformat() if payload.locks_at else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        total_users = sum(outcome.users for outcome in payload.outcomes)
        total_points = sum(outcome.channel_points for outcome in payload.outcomes)
        logger.info(
            f"Processed ChannelPredictionProgress: '{payload.title}' has {total_users} users and {total_points} points"
        )

    async def _handle_prediction_lock(self, event_type: str, payload):
        """Handle ChannelPredictionLock payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.color,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                    "top_predictors": [
                        {
                            "user_id": p.user.id,
                            "user_name": p.user.name,
                            "user_login": (await p.user.user()).name
                            if p.user
                            else None,
                            "channel_points_used": p.channel_points_used,
                            "channel_points_won": p.channel_points_won,
                        }
                        for p in outcome.top_predictors
                    ]
                    if outcome.top_predictors
                    else [],
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "locked_at": payload.locked_at.isoformat() if payload.locked_at else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelPredictionLock: '{payload.title}' prediction locked"
        )

    async def _handle_prediction_end(self, event_type: str, payload):
        """Handle ChannelPredictionEnd payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.color,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                    "top_predictors": [
                        {
                            "user_id": p.user.id,
                            "user_name": p.user.name,
                            "user_login": (await p.user.user()).name
                            if p.user
                            else None,
                            "channel_points_used": p.channel_points_used,
                            "channel_points_won": p.channel_points_won,
                        }
                        for p in outcome.top_predictors
                    ]
                    if outcome.top_predictors
                    else [],
                }
                for outcome in payload.outcomes
            ],
            "status": payload.status,
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "ended_at": payload.ended_at.isoformat() if payload.ended_at else None,
            "winning_outcome_id": payload.winning_outcome_id,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        winning_outcome = (
            next(
                (o for o in payload.outcomes if o.id == payload.winning_outcome_id),
                None,
            )
            if payload.winning_outcome_id
            else None
        )
        winner_info = f" - Winner: '{winning_outcome.title}'" if winning_outcome else ""
        logger.info(
            f"Processed ChannelPredictionEnd: '{payload.title}' prediction ended with status {payload.status}{winner_info}"
        )

    async def _handle_hype_train_begin(self, event_type: str, payload):
        """Handle HypeTrainBegin payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "progress": payload.progress,
            "goal": payload.goal,
            "top_contributions": [
                {
                    "user_id": contrib.user.id,
                    "user_name": contrib.user.name,
                    "user_login": (await contrib.user.user()).name
                    if contrib.user
                    else None,
                    "type": contrib.type,
                    "total": contrib.total,
                }
                for contrib in payload.top_contributions
            ]
            if payload.top_contributions
            else [],
            "last_contribution": {
                "user_id": payload.last_contribution.user.id,
                "user_name": payload.last_contribution.user.name,
                "user_login": (await payload.last_contribution.user.user()).name
                if payload.last_contribution and payload.last_contribution.user
                else None,
                "type": payload.last_contribution.type,
                "total": payload.last_contribution.total,
            }
            if payload.last_contribution
            else None,
            "level": payload.level,
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "expires_at": payload.expires_at.isoformat()
            if payload.expires_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed HypeTrainBegin: Level {payload.level} hype train started - {payload.progress}/{payload.goal}"
        )

    async def _handle_hype_train_progress(self, event_type: str, payload):
        """Handle HypeTrainProgress payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "progress": payload.progress,
            "goal": payload.goal,
            "top_contributions": [
                {
                    "user_id": contrib.user.id,
                    "user_name": contrib.user.name,
                    "user_login": (await contrib.user.user()).name
                    if contrib.user
                    else None,
                    "type": contrib.type,
                    "total": contrib.total,
                }
                for contrib in payload.top_contributions
            ]
            if payload.top_contributions
            else [],
            "last_contribution": {
                "user_id": payload.last_contribution.user.id,
                "user_name": payload.last_contribution.user.name,
                "user_login": (await payload.last_contribution.user.user()).name
                if payload.last_contribution and payload.last_contribution.user
                else None,
                "type": payload.last_contribution.type,
                "total": payload.last_contribution.total,
            }
            if payload.last_contribution
            else None,
            "level": payload.level,
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "expires_at": payload.expires_at.isoformat()
            if payload.expires_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed HypeTrainProgress: Level {payload.level} - {payload.progress}/{payload.goal}"
        )

    async def _handle_hype_train_end(self, event_type: str, payload):
        """Handle HypeTrainEnd payload with its specific structure."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "level": payload.level,
            "top_contributions": [
                {
                    "user_id": contrib.user.id,
                    "user_name": contrib.user.name,
                    "user_login": (await contrib.user.user()).name
                    if contrib.user
                    else None,
                    "type": contrib.type,
                    "total": contrib.total,
                }
                for contrib in payload.top_contributions
            ]
            if payload.top_contributions
            else [],
            "started_at": payload.started_at.isoformat()
            if payload.started_at
            else None,
            "ended_at": payload.ended_at.isoformat() if payload.ended_at else None,
            "cooldown_ends_at": payload.cooldown_ends_at.isoformat()
            if payload.cooldown_ends_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed HypeTrainEnd: Level {payload.level} hype train ended with {payload.total} total"
        )

    async def _handle_goal_begin(self, event_type: str, payload):
        """Handle GoalBegin payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "type": payload.type if hasattr(payload, "type") else None,
            "description": payload.description
            if hasattr(payload, "description")
            else None,
            "current_amount": payload.current_amount
            if hasattr(payload, "current_amount")
            else None,
            "target_amount": payload.target_amount
            if hasattr(payload, "target_amount")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed GoalBegin: {payload_dict.get('type')} goal '{payload_dict.get('description')}' started - {payload_dict.get('current_amount')}/{payload_dict.get('target_amount')}"
        )

    async def _handle_goal_progress(self, event_type: str, payload):
        """Handle GoalProgress payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "type": payload.type if hasattr(payload, "type") else None,
            "description": payload.description
            if hasattr(payload, "description")
            else None,
            "current_amount": payload.current_amount
            if hasattr(payload, "current_amount")
            else None,
            "target_amount": payload.target_amount
            if hasattr(payload, "target_amount")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed GoalProgress: {payload_dict.get('type')} goal '{payload_dict.get('description')}' - {payload_dict.get('current_amount')}/{payload_dict.get('target_amount')}"
        )

    async def _handle_goal_end(self, event_type: str, payload):
        """Handle GoalEnd payload with its specific structure."""
        payload_dict = {
            "id": payload.id if hasattr(payload, "id") else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "type": payload.type if hasattr(payload, "type") else None,
            "description": payload.description
            if hasattr(payload, "description")
            else None,
            "is_achieved": payload.is_achieved
            if hasattr(payload, "is_achieved")
            else None,
            "current_amount": payload.current_amount
            if hasattr(payload, "current_amount")
            else None,
            "target_amount": payload.target_amount
            if hasattr(payload, "target_amount")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "ended_at": payload.ended_at.isoformat()
            if hasattr(payload, "ended_at") and payload.ended_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        status = "achieved" if payload_dict.get("is_achieved") else "ended"
        logger.info(
            f"Processed GoalEnd: {payload_dict.get('type')} goal '{payload_dict.get('description')}' {status} - {payload_dict.get('current_amount')}/{payload_dict.get('target_amount')}"
        )

    async def _handle_ad_break_begin(self, event_type: str, payload):
        """Handle ChannelAdBreakBegin payload with its specific structure."""
        payload_dict = {
            "duration_seconds": payload.duration_seconds
            if hasattr(payload, "duration_seconds")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "is_automatic": payload.is_automatic
            if hasattr(payload, "is_automatic")
            else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "requester_user_id": payload.requester.id
            if hasattr(payload, "requester") and payload.requester
            else None,
            "requester_user_name": payload.requester.name
            if hasattr(payload, "requester") and payload.requester
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        ad_type = (
            "automatic"
            if payload_dict.get("is_automatic")
            else f"manual by {payload_dict.get('requester_user_name')}"
        )
        logger.info(
            f"Processed ChannelAdBreakBegin: {payload_dict.get('duration_seconds')}s {ad_type} ad break started"
        )

    async def _handle_vip_add(self, event_type: str, payload):
        """Handle ChannelVIPAdd payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id
            if hasattr(payload, "user") and payload.user
            else None,
            "user_name": payload.user.name
            if hasattr(payload, "user") and payload.user
            else None,
            "user_login": (await payload.user.user()).name
            if hasattr(payload, "user") and payload.user
            else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelVIPAdd: {payload_dict.get('user_name')} added as VIP"
        )

    async def _handle_vip_remove(self, event_type: str, payload):
        """Handle ChannelVIPRemove payload with its specific structure."""
        payload_dict = {
            "user_id": payload.user.id
            if hasattr(payload, "user") and payload.user
            else None,
            "user_name": payload.user.name
            if hasattr(payload, "user") and payload.user
            else None,
            "user_login": (await payload.user.user()).name
            if hasattr(payload, "user") and payload.user
            else None,
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ChannelVIPRemove: {payload_dict.get('user_name')} removed as VIP"
        )

    async def _handle_shoutout_create(self, event_type: str, payload):
        """Handle ShoutoutCreate payload with its specific structure."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "broadcaster_user_name": payload.broadcaster.name
            if hasattr(payload, "broadcaster") and payload.broadcaster
            else None,
            "to_broadcaster_user_id": payload.to_broadcaster.id
            if hasattr(payload, "to_broadcaster") and payload.to_broadcaster
            else None,
            "to_broadcaster_user_name": payload.to_broadcaster.name
            if hasattr(payload, "to_broadcaster") and payload.to_broadcaster
            else None,
            "moderator_user_id": payload.moderator.id
            if hasattr(payload, "moderator") and payload.moderator
            else None,
            "moderator_user_name": payload.moderator.name
            if hasattr(payload, "moderator") and payload.moderator
            else None,
            "viewer_count": payload.viewer_count
            if hasattr(payload, "viewer_count")
            else None,
            "started_at": payload.started_at.isoformat()
            if hasattr(payload, "started_at") and payload.started_at
            else None,
            "cooldown_ends_at": payload.cooldown_ends_at.isoformat()
            if hasattr(payload, "cooldown_ends_at") and payload.cooldown_ends_at
            else None,
            "target_cooldown_ends_at": payload.target_cooldown_ends_at.isoformat()
            if hasattr(payload, "target_cooldown_ends_at")
            and payload.target_cooldown_ends_at
            else None,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"Processed ShoutoutCreate: {payload_dict.get('broadcaster_user_name')} shouted out {payload_dict.get('to_broadcaster_user_name')} to {payload_dict.get('viewer_count')} viewers"
        )

    async def _handle_limit_break_update(self, payload):
        """Handle limit break updates when 'Throw Something At Me' reward events occur."""
        # The reward ID for "Throw Something At Me"
        THROW_REWARD_ID = "5685d03e-80c2-4640-ba06-566fb8bbc4ce"

        # Check if this event is for our target reward
        reward_id = None
        if hasattr(payload, "reward") and hasattr(payload.reward, "id"):
            reward_id = payload.reward.id

        if reward_id != THROW_REWARD_ID:
            return  # Not the reward we care about

        try:
            # Get current queue count from helix service
            from shared.services.twitch.helix import helix_service

            count = await helix_service.get_reward_redemption_count(THROW_REWARD_ID)

            # Calculate limit break state (3 bars: 33/66/100)
            bar1_fill = min(count / 33, 1.0)
            bar2_fill = min(max(count - 33, 0) / 33, 1.0) if count > 33 else 0
            bar3_fill = min(max(count - 66, 0) / 34, 1.0) if count > 66 else 0
            is_maxed = count >= 100

            limit_break_data = {
                "count": count,
                "bars": {"bar1": bar1_fill, "bar2": bar2_fill, "bar3": bar3_fill},
                "is_maxed": is_maxed,
                "sound_trigger": count >= 100,  # Trigger sound when hitting 100
            }

            # Publish to Redis for overlay consumers
            redis_conn = redis.from_url(settings.REDIS_URL)
            await redis_conn.publish(
                "events:limitbreak",
                json.dumps(
                    {
                        "event_type": "limitbreak.update",
                        "data": limit_break_data,
                        "timestamp": timezone.now().isoformat(),
                    }
                ),
            )
            await redis_conn.close()

            logger.info(
                f"Limit break update: {count} redemptions, bars: {bar1_fill:.2f}/{bar2_fill:.2f}/{bar3_fill:.2f}, maxed: {is_maxed}"
            )

        except Exception as e:
            logger.error(f"Error handling limit break update: {e}")

    async def _publish_to_redis(
        self,
        event_type: str,
        event: Event,
        member: Member | None,
        payload_dict: dict,
    ):
        """Publish event to Redis for real-time broadcasting."""
        try:
            redis_message = {
                "event_id": str(event.id),
                "event_type": event_type,
                "source": "twitch",
                "timestamp": event.timestamp.isoformat(),
                "member": {
                    "id": str(member.id),
                    "twitch_id": member.twitch_id,
                    "username": member.username,
                    "display_name": member.display_name,
                }
                if member
                else None,
                "payload": payload_dict,
            }

            # Publish to general events channel
            channel = "events:twitch"
            message_json = json.dumps(redis_message)

            # Publish directly with async Redis client
            await self._redis_client.publish(channel, message_json)

            logger.debug(f"Published {event_type} event to Redis channel: {channel}")

        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")

    async def _get_or_create_member_from_payload(self, payload) -> Member | None:
        """Extract Member information from EventSub payload using proper TwitchIO object-based access."""
        user_obj = None

        # Determine the primary user object based on priority
        if hasattr(payload, "user") and payload.user:
            user_obj = payload.user
        elif hasattr(payload, "chatter") and payload.chatter:
            user_obj = payload.chatter
        elif hasattr(payload, "from_broadcaster") and payload.from_broadcaster:
            user_obj = payload.from_broadcaster
        elif hasattr(payload, "broadcaster") and payload.broadcaster:
            user_obj = payload.broadcaster

        if user_obj:
            twitch_id = str(getattr(user_obj, "id", ""))
            username = getattr(user_obj, "login", getattr(user_obj, "name", None))
            display_name = getattr(
                user_obj, "display_name", getattr(user_obj, "name", None)
            )
        else:
            return None

        if not twitch_id:
            return None

        # Use update_or_create to avoid race conditions
        defaults = {
            "username": username or "",
            "display_name": display_name or username or f"User_{twitch_id}",
        }

        member, _ = await sync_to_async(Member.objects.update_or_create)(
            twitch_id=twitch_id,
            defaults=defaults,
        )

        return member

    async def _create_event(
        self,
        event_type: str,
        payload: dict,
        member: Member | None,
    ) -> Event:
        """Create Event record using sync_to_async."""
        # Get or create session based on stream state, not just date
        session = None
        from django.utils import timezone as django_timezone

        from streams.models import Session

        if event_type == "stream.online":
            # Create session for stream start date and store in Redis
            stream_date = django_timezone.now().date()
            try:
                session, created = await sync_to_async(Session.objects.get_or_create)(
                    session_date=stream_date
                )
                logger.info(
                    f"Session for {stream_date}: {'created' if created else 'found existing'}"
                )

                # Store session ID in Redis with 12-hour TTL
                redis_key = "twitch:active_session"
                ttl_seconds = 12 * 60 * 60  # 12 hours
                await self._redis_client.set(redis_key, str(session.id), ex=ttl_seconds)
                logger.info(
                    f"Stored active session {session.id} in Redis with {ttl_seconds}s TTL"
                )

            except Exception as e:
                logger.error(f"Failed to get_or_create session for {stream_date}: {e}")
                logger.error(f"Exception type: {type(e)}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                session = None
        elif event_type == "stream.offline":
            # Keep the session active for 30 minutes after stream.offline
            # This allows post-stream events (raids, etc.) to be associated with the stream
            # Also handles errant offline events where stream comes back online
            try:
                redis_key = "twitch:active_session"
                session_id = await self._redis_client.get(redis_key)
                if session_id:
                    session = await sync_to_async(Session.objects.filter(id=session_id).first)()
                    if session:
                        # Set expiry to 30 minutes from now
                        ttl_seconds = 30 * 60  # 30 minutes
                        await self._redis_client.expire(redis_key, ttl_seconds)
                        logger.info(f"Stream offline but keeping session {session.id} active for {ttl_seconds/60:.0f} more minutes for post-stream events")
                    else:
                        logger.warning(f"Session {session_id} from Redis not found in database")
                        session = None
                else:
                    logger.info("No active session in Redis during stream.offline")
                    session = None
            except Exception as e:
                logger.error(f"Error handling session during stream.offline: {e}")
                session = None
        else:
            # For all other events, check Redis first for active session
            try:
                redis_key = "twitch:active_session"
                session_id = await self._redis_client.get(redis_key)

                if session_id:
                    # Found active session in Redis
                    session_id_str = (
                        session_id.decode("utf-8")
                        if isinstance(session_id, bytes)
                        else session_id
                    )
                    session = await sync_to_async(Session.objects.get)(
                        id=session_id_str
                    )
                    logger.debug(f"Using active session {session_id_str} from Redis")
                else:
                    # Redis miss - check database for recent active session
                    logger.debug(
                        "No session in Redis, checking database for recent session"
                    )

                    # Look for a session created today or yesterday (to handle UTC boundary)
                    from datetime import timedelta

                    today = django_timezone.now().date()
                    yesterday = today - timedelta(days=1)

                    recent_session = await sync_to_async(
                        lambda: Session.objects.filter(
                            session_date__in=[today, yesterday]
                        )
                        .order_by("-session_date")
                        .first()
                    )()

                    if recent_session:
                        # Found recent session, populate Redis
                        session = recent_session
                        ttl_seconds = 12 * 60 * 60  # 12 hours
                        await self._redis_client.set(
                            redis_key, str(session.id), ex=ttl_seconds
                        )
                        logger.info(
                            f"Populated Redis with recent session {session.id} from database"
                        )
                    else:
                        logger.debug("No recent session found in database")
                        session = None

            except Exception as e:
                logger.error(f"Error finding active session: {e}")
                session = None

        # Fallback: If no session found and not offline event, create one for current date
        if not session and event_type != "stream.offline":
            try:
                current_date = timezone.now().date()

                session, created = await sync_to_async(Session.objects.get_or_create)(
                    session_date=current_date
                )
                if created:
                    logger.warning(
                        f"Created fallback session for {current_date} due to missing active session"
                    )
                else:
                    logger.info(
                        f"Using existing session for {current_date} as fallback"
                    )

                # Store in Redis for future events
                if session:
                    redis_key = "twitch:active_session"
                    ttl_seconds = 12 * 60 * 60  # 12 hours
                    await self._redis_client.set(
                        redis_key, str(session.id), ex=ttl_seconds
                    )
                    logger.info(f"Stored fallback session {session.id} in Redis")

            except Exception as e:
                logger.error(f"Failed to create fallback session: {e}")
                session = None

        return await sync_to_async(Event.objects.create)(
            source="twitch",
            event_type=event_type,
            member=member,
            session=session,
            payload=payload,
            timestamp=timezone.now(),
        )
