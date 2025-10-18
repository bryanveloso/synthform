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

from campaigns.services import campaign_service  # noqa: E402
from events.models import Event  # noqa: E402
from events.models import Member  # noqa: E402
from streams.services.obs import obs_service  # noqa: E402

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

        logger.info("[TwitchIO] TwitchEventHandler initialized.")

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

    # Public event methods for TwitchIO integration
    async def event_follow(self, payload):
        """Handle channel follow events."""
        await self._create_event_from_payload("channel.follow", payload)

    async def event_subscription(self, payload):
        """Handle channel subscription events."""
        await self._create_event_from_payload("channel.subscribe", payload)

    async def event_subscription_gift(self, payload):
        """Handle channel subscription gift events."""
        await self._create_event_from_payload("channel.subscription.gift", payload)

    async def event_subscription_end(self, payload):
        """Handle channel subscription end events."""
        await self._create_event_from_payload("channel.subscription.end", payload)

    async def event_subscription_message(self, payload):
        """Handle channel subscription message events."""
        await self._create_event_from_payload("channel.subscription.message", payload)

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
        # Track stream status in Redis for ad scheduler
        await self._redis_client.set("stream:live", "true")
        logger.info("[Stream] Stream is now live")

    async def event_stream_offline(self, payload):
        """Handle stream offline events."""
        await self._create_event_from_payload("stream.offline", payload)
        # Track stream status in Redis for ad scheduler
        await self._redis_client.set("stream:live", "false")
        logger.info("[Stream] Stream is now offline")

    async def event_channel_update(self, payload):
        """Handle channel update events."""
        await self._create_event_from_payload("channel.update", payload)

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

    async def event_poll_begin(self, payload):
        """Handle poll begin events."""
        await self._create_event_from_payload("channel.poll.begin", payload)

    async def event_poll_progress(self, payload):
        """Handle poll progress events."""
        await self._create_event_from_payload("channel.poll.progress", payload)

    async def event_poll_end(self, payload):
        """Handle poll end events."""
        await self._create_event_from_payload("channel.poll.end", payload)

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

    async def event_hype_train_begin(self, payload):
        """Handle hype train begin events."""
        await self._create_event_from_payload("channel.hype_train.begin", payload)

    async def event_hype_train_progress(self, payload):
        """Handle hype train progress events."""
        await self._create_event_from_payload("channel.hype_train.progress", payload)

    async def event_hype_train_end(self, payload):
        """Handle hype train end events."""
        await self._create_event_from_payload("channel.hype_train.end", payload)

    async def event_goal_begin(self, payload):
        """Handle goal begin events."""
        await self._create_event_from_payload("channel.goal.begin", payload)

    async def event_goal_progress(self, payload):
        """Handle goal progress events."""
        await self._create_event_from_payload("channel.goal.progress", payload)

    async def event_goal_end(self, payload):
        """Handle goal end events."""
        await self._create_event_from_payload("channel.goal.end", payload)

    async def event_ad_break(self, payload):
        """Handle ad break events."""
        await self._create_event_from_payload("channel.ad_break.begin", payload)

    async def event_vip_add(self, payload):
        """Handle VIP add events."""
        await self._create_event_from_payload("channel.vip.add", payload)

    async def event_vip_remove(self, payload):
        """Handle VIP remove events."""
        await self._create_event_from_payload("channel.vip.remove", payload)

    async def event_shoutout_create(self, payload):
        """Handle shoutout create events."""
        await self._create_event_from_payload("channel.shoutout.create", payload)

    async def _create_event_from_payload(self, event_type: str, payload):
        """Dispatcher - route to type-specific handler based on payload class."""
        payload_class = type(payload)
        logger.info(
            f"[TwitchIO] Processing event. type={event_type} payload_class={payload_class.__name__}"
        )

        # Find the appropriate handler for this payload type
        handler = self.EVENT_HANDLERS.get(payload_class)
        if handler:
            logger.info(
                f"[TwitchIO] Handler found. payload_class={payload_class.__name__} handler={handler.__name__}"
            )
            return await handler(event_type, payload)
        else:
            logger.error(
                f"[TwitchIO] ❌ No handler found for payload type. payload_class={payload_class.__name__}"
            )
            logger.error(
                f"[TwitchIO] Available handlers: {[cls.__name__ for cls in self.EVENT_HANDLERS.keys()]}"
            )

    # Type-specific payload handlers - trust TwitchIO's structure
    async def _handle_chat_message(self, event_type: str, payload):
        """Handle ChatMessage payload."""
        payload_dict = {
            "id": payload.id,
            "text": payload.text,
            "type": payload.type,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "user_id": payload.chatter.id,
            "user_name": payload.chatter.name,
            "user_display_name": payload.chatter.display_name,
            "colour": str(payload.colour),
            "badges": [
                {"set_id": badge.set_id, "id": badge.id, "info": badge.info}
                for badge in payload.badges
            ],
            "fragments": [
                {
                    "type": fragment.type,
                    "text": fragment.text,
                    "emote": {
                        "id": fragment.emote.id,
                        "emote_set_id": fragment.emote.set_id,
                    }
                    if hasattr(fragment, "emote") and fragment.emote
                    else None,
                }
                for fragment in payload.fragments
            ],
            "subscriber": payload.chatter.subscriber,
            "moderator": payload.chatter.moderator,
            "broadcaster": payload.chatter.broadcaster,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChatMessage. user={payload.chatter.display_name} text="{payload.text[:50]}..."'
        )

    async def _handle_chat_notification(self, event_type: str, payload):
        """Handle ChatNotification payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "chatter_user_id": payload.chatter.id,
            "chatter_user_name": payload.chatter.name,
            "chatter_display_name": payload.chatter.display_name,
            "chatter_is_anonymous": payload.anonymous,
            "color": str(payload.colour),
            "badges": [
                {"set_id": badge.set_id, "id": badge.id, "info": badge.info}
                for badge in payload.badges
            ],
            "system_message": payload.system_message,
            "message_id": payload.id,
            "message": {
                "text": payload.text,
                "fragments": [
                    {
                        "type": frag.type,
                        "text": frag.text,
                        # Handle emote data if present
                        "emote": {
                            "id": frag.emote.id
                            if hasattr(frag, "emote") and frag.emote
                            else None,
                            "set_id": frag.emote.emote_set_id
                            if hasattr(frag, "emote")
                            and frag.emote
                            and hasattr(frag.emote, "emote_set_id")
                            else None,
                        }
                        if hasattr(frag, "emote") and frag.emote
                        else None,
                    }
                    for frag in payload.fragments
                ],
            },
            "notice_type": payload.notice_type,
        }

        # Add notice-type specific data if present
        # These fields contain the detailed information for each notice type
        notice_fields = [
            "sub",  # New subscription data
            "resub",  # Resubscription data
            "sub_gift",  # Gift subscription data
            "community_sub_gift",  # Community gift data
            "gift_paid_upgrade",  # Gift upgrade data
            "prime_paid_upgrade",  # Prime upgrade data
            "raid",  # Raid data
            "unraid",  # Unraid data (always None but we capture it)
            "pay_it_forward",  # Pay it forward data
            "announcement",  # Announcement data
            "bits_badge_tier",  # Bits badge data
            "charity_donation",  # Charity donation data
            # Shared chat variants (for multi-channel streaming)
            "shared_sub",  # Shared chat subscription
            "shared_resub",  # Shared chat resubscription
            "shared_sub_gift",  # Shared chat gift subscription
            "shared_community_sub_gift",  # Shared chat community gift
            "shared_gift_paid_upgrade",  # Shared chat gift upgrade
            "shared_prime_paid_upgrade",  # Shared chat prime upgrade
            "shared_raid",  # Shared chat raid
            "shared_pay_it_forward",  # Shared chat pay it forward
            "shared_announcement",  # Shared chat announcement
        ]

        def serialize_twitchio_object(obj):
            """Safely serialize TwitchIO objects to dict, excluding internal properties."""
            if obj is None:
                return None

            # Handle primitive types
            if isinstance(obj, (str, int, float, bool)):
                return obj

            # Handle lists
            if isinstance(obj, list):
                return [serialize_twitchio_object(item) for item in obj]

            # Handle dicts
            if isinstance(obj, dict):
                return {
                    k: serialize_twitchio_object(v)
                    for k, v in obj.items()
                    if not k.startswith("_")
                }

            # Handle TwitchIO objects
            result = {}

            # Check if object uses __slots__ (common in TwitchIO)
            if hasattr(obj, "__slots__"):
                logger.debug(
                    f"Serializing {type(obj).__name__} with __slots__: {obj.__slots__}"
                )
                for slot in obj.__slots__:
                    # Skip private/internal attributes
                    if slot.startswith("_"):
                        continue
                    try:
                        attr_value = getattr(obj, slot)
                        if attr_value is not None:
                            # Skip internal TwitchIO objects
                            if slot in [
                                "_http",
                                "_session",
                                "_client_id",
                                "_session_set",
                                "_should_close",
                            ]:
                                continue
                            logger.debug(
                                f"  Slot '{slot}' = {attr_value!r} ({type(attr_value).__name__})"
                            )
                            # Recursively serialize nested objects
                            result[slot] = serialize_twitchio_object(attr_value)
                    except AttributeError:
                        # Slot exists but not set
                        logger.debug(f"  Slot '{slot}' not set")
                        continue
            # Fallback to __dict__ for regular objects
            elif hasattr(obj, "__dict__"):
                for key, value in obj.__dict__.items():
                    # Skip private attributes and None values
                    if key.startswith("_") or value is None:
                        continue
                    # Skip internal TwitchIO properties
                    if key in [
                        "_http",
                        "_session",
                        "_client_id",
                        "_session_set",
                        "_should_close",
                        "_url",
                        "_ext",
                        "_original_url",
                        "user_agent",
                    ]:
                        continue
                    result[key] = serialize_twitchio_object(value)
            else:
                # If neither __slots__ nor __dict__, convert to string
                return str(obj)

            return result if result else None

        # Track community gift ID for aggregation
        community_gift_id = None

        for field in notice_fields:
            if hasattr(payload, field):
                field_value = getattr(payload, field)
                if field_value is not None:
                    logger.debug(
                        f"Processing notice field '{field}' for {payload.notice_type}"
                    )
                    serialized_field = serialize_twitchio_object(field_value)
                    payload_dict[field] = serialized_field

                    # Extract community_gift_id from community_sub_gift or sub_gift
                    if field in ["community_sub_gift", "sub_gift"] and serialized_field:
                        # Check if this field contains a community_gift_id
                        if isinstance(serialized_field, dict):
                            if "community_gift_id" in serialized_field:
                                community_gift_id = serialized_field[
                                    "community_gift_id"
                                ]
                            elif (
                                "id" in serialized_field
                                and field == "community_sub_gift"
                            ):
                                # For community_sub_gift, the ID is the community_gift_id
                                community_gift_id = serialized_field["id"]
                                serialized_field["community_gift_id"] = (
                                    community_gift_id
                                )
                else:
                    payload_dict[field] = None

        # Add community_gift_id to the main payload if found
        if community_gift_id:
            payload_dict["community_gift_id"] = community_gift_id

        # Extract tier information from serialized data
        tier = None
        if "sub_gift" in payload_dict and isinstance(payload_dict["sub_gift"], dict):
            tier = payload_dict["sub_gift"].get("tier")
        elif "community_sub_gift" in payload_dict and isinstance(
            payload_dict["community_sub_gift"], dict
        ):
            tier = payload_dict["community_sub_gift"].get("tier")
        elif "sub" in payload_dict and isinstance(payload_dict["sub"], dict):
            tier = payload_dict["sub"].get("tier")
        elif "resub" in payload_dict and isinstance(payload_dict["resub"], dict):
            tier = payload_dict["resub"].get("tier")

        if tier:
            payload_dict["tier"] = tier

        # Suppress alerts for gift recipients (community_sub_gift has the total)
        if payload.notice_type == "sub_gift" and community_gift_id is not None:
            payload_dict["suppress_alert"] = True

        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        await self._publish_to_redis(event_type, event, member, payload_dict)

        if payload_dict.get("suppress_alert"):
            logger.info(
                f"[TwitchIO] Processed ChatNotification (suppressed alert). user={payload.chatter.display_name} type={payload.notice_type}"
            )
        else:
            logger.info(
                f"[TwitchIO] Processed ChatNotification. user={payload.chatter.display_name} type={payload.notice_type}"
            )

    async def _handle_chat_message_delete(self, event_type: str, payload):
        """Handle ChatMessageDelete payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "target_user_id": payload.user.id,
            "target_user_name": payload.user.name,
            "message_id": payload.message_id,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(f"[TwitchIO] Processed ChatMessageDelete. user={payload.user.name}")

    async def _handle_chat_clear(self, event_type: str, payload):
        """Handle ChannelChatClear payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelChatClear. broadcaster={payload.broadcaster.name}"
        )

    async def _handle_chat_clear_user(self, event_type: str, payload):
        """Handle ChannelChatClearUserMessages payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "target_user_id": payload.user.id,
            "target_user_name": payload.user.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelChatClearUserMessages. user={payload.user.name}"
        )

    async def _handle_channel_follow(self, event_type: str, payload):
        """Handle ChannelFollow payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_display_name": payload.user.display_name,
            "followed_at": payload.followed_at.isoformat(),
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelFollow. user={payload.user.display_name}"
        )

    async def _handle_channel_update(self, event_type: str, payload):
        """Handle ChannelUpdate payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "language": payload.language,
            "category_id": payload.category_id,
            "category_name": payload.category_name,
            "content_classification_labels": payload.content_classification_labels,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelUpdate. broadcaster={payload.broadcaster.name} title="{payload.title}" category={payload.category_name}'
        )

    async def _handle_channel_cheer(self, event_type: str, payload):
        """Handle ChannelCheer payload."""
        payload_dict = {
            "bits": payload.bits,
            "message": payload.message,
            "is_anonymous": payload.anonymous,
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "user_display_name": payload.user.display_name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track campaign metrics for bits
        active_campaign = await campaign_service.get_active_campaign()
        if active_campaign:
            campaign_result = await campaign_service.process_bits(
                active_campaign, bits=payload.bits
            )
            if campaign_result:
                payload_dict["campaign_data"] = campaign_result

        await self._publish_to_redis(event_type, event, member, payload_dict)
        user_name = "Anonymous" if payload.anonymous else payload.user.name
        logger.info(
            f"[TwitchIO] Processed ChannelCheer. user={user_name} bits={payload.bits}"
        )

    async def _handle_channel_raid(self, event_type: str, payload):
        """Handle ChannelRaid payload."""
        payload_dict = {
            "from_broadcaster_user_id": payload.from_broadcaster.id,
            "from_broadcaster_user_name": payload.from_broadcaster.name,
            "from_broadcaster_user_display_name": payload.from_broadcaster.display_name,
            "to_broadcaster_user_id": payload.to_broadcaster.id,
            "to_broadcaster_user_name": payload.to_broadcaster.name,
            "to_broadcaster_user_display_name": payload.to_broadcaster.display_name,
            "viewers": payload.viewer_count,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelRaid. from={payload.from_broadcaster.name} viewers={payload.viewer_count}"
        )

    async def _handle_channel_ban(self, event_type: str, payload):
        """Handle ChannelBan payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "moderator_user_id": payload.moderator.id,
            "moderator_user_name": payload.moderator.name,
            "reason": payload.reason,
            "banned_at": payload.banned_at.isoformat(),
            "ends_at": payload.ends_at.isoformat() if payload.ends_at else None,
            "is_permanent": payload.permanent,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        ban_type = "permanently" if payload.permanent else f"until {payload.ends_at}"
        logger.info(
            f"[TwitchIO] Processed ChannelBan. user={payload.user.name} type={ban_type} moderator={payload.moderator.name}"
        )

    async def _handle_channel_unban(self, event_type: str, payload):
        """Handle ChannelUnban payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "moderator_user_id": payload.moderator.id,
            "moderator_user_name": payload.moderator.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelUnban. user={payload.user.name} moderator={payload.moderator.name}"
        )

    async def _handle_channel_subscribe(self, event_type: str, payload):
        """Handle ChannelSubscribe payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_display_name": payload.user.display_name,
            "tier": payload.tier,
            "is_gift": payload.gift,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track campaign metrics - only for direct subscriptions (not gifts)
        # Gift subscriptions are counted in _handle_channel_subscription_gift
        active_campaign = await campaign_service.get_active_campaign()
        if active_campaign and not payload.gift:
            campaign_result = await campaign_service.process_subscription(
                active_campaign, tier=payload.tier, is_gift=False
            )

            # Add campaign data to payload for Redis
            if campaign_result:
                payload_dict["campaign_data"] = campaign_result

                # If a milestone was unlocked, publish special event
                if "milestone_unlocked" in campaign_result:
                    await self._publish_to_redis(
                        "campaign.milestone.unlocked",
                        event,
                        member,
                        campaign_result["milestone_unlocked"],
                    )

        # Only publish to Redis if it's not a gift subscription
        # Gift subscriptions are published via channel.subscription.gift event
        if not payload.gift:
            await self._publish_to_redis(event_type, event, member, payload_dict)
            logger.info(
                f"[TwitchIO] Processed ChannelSubscribe. user={payload.user.name} tier={payload.tier}"
            )
        else:
            logger.info(
                f"[TwitchIO] Processed ChannelSubscribe (gift recipient, skipped alert). user={payload.user.name}"
            )

    async def _handle_channel_subscription_end(self, event_type: str, payload):
        """Handle ChannelSubscriptionEnd payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "tier": payload.tier,
            "is_gift": payload.gift,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelSubscriptionEnd. user={payload.user.name} tier={payload.tier}"
        )

    async def _handle_channel_subscription_gift(self, event_type: str, payload):
        """Handle ChannelSubscriptionGift payload."""
        payload_dict = {
            "user_id": payload.user.id if payload.user else None,
            "user_name": payload.user.name if payload.user else None,
            "user_display_name": payload.user.display_name if payload.user else None,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
            "total": payload.total,
            "tier": payload.tier,
            "cumulative_total": payload.cumulative_total,
            "is_anonymous": payload.anonymous,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track campaign metrics - process each gift sub
        active_campaign = await campaign_service.get_active_campaign()
        if active_campaign:
            milestones_unlocked = []
            for _ in range(payload.total):
                campaign_result = await campaign_service.process_subscription(
                    active_campaign,
                    tier=payload.tier,
                    is_gift=True,
                    gifter_id=payload.user.id if payload.user else None,
                    gifter_name=payload.user.display_name if payload.user else None,
                )

                # Collect any milestones that were unlocked
                if campaign_result and "milestone_unlocked" in campaign_result:
                    milestones_unlocked.append(campaign_result["milestone_unlocked"])

            # Add campaign data to payload
            if milestones_unlocked:
                payload_dict["milestones_unlocked"] = milestones_unlocked
                # Publish milestone unlock events
                for milestone in milestones_unlocked:
                    await self._publish_to_redis(
                        "campaign.milestone.unlocked", event, member, milestone
                    )

        await self._publish_to_redis(event_type, event, member, payload_dict)
        user_name = "Anonymous" if payload.anonymous else payload.user.name
        logger.info(
            f"[TwitchIO] Processed ChannelSubscriptionGift. user={user_name} count={payload.total}"
        )

    async def _handle_channel_subscription_message(self, event_type: str, payload):
        """Handle ChannelSubscriptionMessage payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_display_name": payload.user.display_name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
            "tier": payload.tier,
            "message": payload.text,
            "cumulative_months": payload.cumulative_months,
            "streak_months": payload.streak_months,
            "duration_months": payload.months,
            "emotes": [
                {
                    "id": emote.id,
                    "begin": emote.begin,
                    "end": emote.end,
                }
                for emote in (payload.emotes or [])
            ]
            if payload.emotes
            else [],
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track campaign metrics for resubs
        active_campaign = await campaign_service.get_active_campaign()
        if active_campaign:
            campaign_result = await campaign_service.process_resub(active_campaign)
            if campaign_result:
                payload_dict["campaign_data"] = campaign_result

        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ChannelSubscriptionMessage. user={payload.user.name} months={payload.cumulative_months}"
        )

    async def _handle_stream_online(self, event_type: str, payload):
        """Handle StreamOnline payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "type": payload.type,
            "started_at": payload.started_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track session start
        from django.utils import timezone

        from streams.models import Session

        today = timezone.now().date()
        session, created = await Session.objects.aget_or_create(
            session_date=today, defaults={"started_at": payload.started_at}
        )
        if not created and not session.started_at:
            # If session exists but hasn't been started yet today
            session.started_at = payload.started_at
            await session.asave()

        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed StreamOnline. broadcaster={payload.broadcaster.name}"
        )

        # Sync campaign state when stream starts
        from campaigns.services import campaign_service

        try:
            await campaign_service.sync_campaign_state()
        except Exception as e:
            logger.error(
                f'[Campaign] ❌ Failed to sync campaign state on stream online. error="{str(e)}"'
            )

        # Reset OBS performance metrics
        try:
            await obs_service.reset_performance_metrics()
        except Exception as e:
            logger.error(
                f'[Streams] ❌ Failed to reset OBS performance metrics on stream online. error="{str(e)}"'
            )

    async def _handle_stream_offline(self, event_type: str, payload):
        """Handle StreamOffline payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)

        # Track session end - find the most recent open session
        from django.utils import timezone

        from streams.models import Session

        # Find the most recent session that has started but not ended
        try:
            session = (
                await Session.objects.filter(
                    started_at__isnull=False, ended_at__isnull=True
                )
                .order_by("-session_date")
                .afirst()
            )

            if session:
                session.ended_at = timezone.now()
                session.duration = session.calculate_duration()
                await session.asave()
                logger.info(
                    f"[Session] Session ended. date={session.session_date} duration={session.duration}s"
                )
            else:
                logger.warning(
                    "[Session] 🟡 No open session found when stream went offline."
                )
        except Exception as e:
            logger.error(
                f'[Session] ❌ Failed to close session on stream offline. error="{str(e)}"'
            )

        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed StreamOffline. broadcaster={payload.broadcaster.name}"
        )

        # Sync campaign state when stream ends
        from campaigns.services import campaign_service

        try:
            await campaign_service.sync_campaign_state()
        except Exception as e:
            logger.error(
                f'[Campaign] ❌ Failed to sync campaign state on stream offline. error="{str(e)}"'
            )

        # Reset OBS performance metrics
        try:
            await obs_service.reset_performance_metrics()
        except Exception as e:
            logger.error(
                f'[Streams] ❌ Failed to reset OBS performance metrics on stream offline. error="{str(e)}"'
            )

    async def _handle_custom_reward_add(self, event_type: str, payload):
        """Handle ChannelPointsRewardAdd payload."""
        payload_dict = {
            "id": payload.reward.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.reward.title,
            "cost": payload.reward.cost,
            "prompt": payload.reward.prompt,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPointsRewardAdd. reward="{payload.reward.title}" cost={payload.reward.cost}'
        )

    async def _handle_custom_reward_update(self, event_type: str, payload):
        """Handle ChannelPointsRewardUpdate payload."""
        payload_dict = {
            "id": payload.reward.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.reward.title,
            "cost": payload.reward.cost,
            "prompt": payload.reward.prompt,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPointsRewardUpdate. reward="{payload.reward.title}"'
        )

    async def _handle_custom_reward_remove(self, event_type: str, payload):
        """Handle ChannelPointsRewardRemove payload."""
        payload_dict = {
            "id": payload.reward.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.reward.title,
            "cost": payload.reward.cost,
            "prompt": payload.reward.prompt,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPointsRewardRemove. reward="{payload.reward.title}"'
        )

    async def _handle_custom_redemption_add(self, event_type: str, payload):
        """Handle ChannelPointsRedemptionAdd payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_display_name": payload.user.display_name,
            "user_input": payload.user_input,
            "status": payload.status,
            "reward": {
                "id": payload.reward.id,
                "title": payload.reward.title,
                "cost": payload.reward.cost,
                "prompt": payload.reward.prompt,
            },
            "redeemed_at": payload.redeemed_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPointsRedemptionAdd. user={payload.user.name} reward="{payload.reward.title}" cost={payload.reward.cost}'
        )

    async def _handle_custom_redemption_update(self, event_type: str, payload):
        """Handle ChannelPointsRedemptionUpdate payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "broadcaster_user_display_name": payload.broadcaster.display_name,
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "user_display_name": payload.user.display_name,
            "user_input": payload.user_input,
            "status": payload.status,
            "reward": {
                "id": payload.reward.id,
                "title": payload.reward.title,
                "cost": payload.reward.cost,
                "prompt": payload.reward.prompt,
            },
            "redeemed_at": payload.redeemed_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPointsRedemptionUpdate. user={payload.user.name} reward="{payload.reward.title}" status={payload.status}'
        )

    async def _handle_poll_begin(self, event_type: str, payload):
        """Handle ChannelPollBegin payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "choices": [
                {
                    "id": choice.id,
                    "title": choice.title,
                    "votes": choice.votes,
                    "channel_points_votes": choice.channel_points_votes,
                }
                for choice in payload.choices
            ],
            "started_at": payload.started_at.isoformat(),
            "ends_at": payload.ends_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPollBegin. title="{payload.title}" choices={len(payload.choices)}'
        )

    async def _handle_poll_progress(self, event_type: str, payload):
        """Handle ChannelPollProgress payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "choices": [
                {
                    "id": choice.id,
                    "title": choice.title,
                    "votes": choice.votes,
                    "channel_points_votes": choice.channel_points_votes,
                }
                for choice in payload.choices
            ],
            "started_at": payload.started_at.isoformat(),
            "ends_at": payload.ends_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        total_votes = sum(choice.votes for choice in payload.choices)
        logger.info(
            f'[TwitchIO] Processed ChannelPollProgress. title="{payload.title}" votes={total_votes}'
        )

    async def _handle_poll_end(self, event_type: str, payload):
        """Handle ChannelPollEnd payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "choices": [
                {
                    "id": choice.id,
                    "title": choice.title,
                    "votes": choice.votes,
                    "channel_points_votes": choice.channel_points_votes,
                }
                for choice in payload.choices
            ],
            "status": payload.status,
            "started_at": payload.started_at.isoformat(),
            "ended_at": payload.ended_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        winning_choice = max(payload.choices, key=lambda c: c.votes)
        logger.info(
            f'[TwitchIO] Processed ChannelPollEnd. title="{payload.title}" winner="{winning_choice.title}" votes={winning_choice.votes}'
        )

    async def _handle_prediction_begin(self, event_type: str, payload):
        """Handle ChannelPredictionBegin payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.colour,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat(),
            "locks_at": payload.locks_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPredictionBegin. title="{payload.title}" outcomes={len(payload.outcomes)}'
        )

    async def _handle_prediction_progress(self, event_type: str, payload):
        """Handle ChannelPredictionProgress payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.colour,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat(),
            "locks_at": payload.locks_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        total_users = sum(outcome.users for outcome in payload.outcomes)
        total_points = sum(outcome.channel_points for outcome in payload.outcomes)
        logger.info(
            f'[TwitchIO] Processed ChannelPredictionProgress. title="{payload.title}" users={total_users} points={total_points}'
        )

    async def _handle_prediction_lock(self, event_type: str, payload):
        """Handle ChannelPredictionLock payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.colour,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                }
                for outcome in payload.outcomes
            ],
            "started_at": payload.started_at.isoformat(),
            "locked_at": payload.locked_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed ChannelPredictionLock. title="{payload.title}"'
        )

    async def _handle_prediction_end(self, event_type: str, payload):
        """Handle ChannelPredictionEnd payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "title": payload.title,
            "outcomes": [
                {
                    "id": outcome.id,
                    "title": outcome.title,
                    "color": outcome.colour,
                    "users": outcome.users,
                    "channel_points": outcome.channel_points,
                }
                for outcome in payload.outcomes
            ],
            "status": payload.status,
            "started_at": payload.started_at.isoformat(),
            "ended_at": payload.ended_at.isoformat(),
            "winning_outcome_id": payload.winning_outcome_id,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        winning_outcome = next(
            (o for o in payload.outcomes if o.id == payload.winning_outcome_id), None
        )
        if winning_outcome:
            logger.info(
                f'[TwitchIO] Processed ChannelPredictionEnd. title="{payload.title}" status={payload.status} winner="{winning_outcome.title}"'
            )
        else:
            logger.info(
                f'[TwitchIO] Processed ChannelPredictionEnd. title="{payload.title}" status={payload.status}'
            )

    async def _handle_hype_train_begin(self, event_type: str, payload):
        """Handle HypeTrainBegin payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "progress": payload.progress,
            "goal": payload.goal,
            "level": payload.level,
            "started_at": payload.started_at.isoformat(),
            "expires_at": payload.expires_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed HypeTrainBegin. level={payload.level} progress={payload.progress} goal={payload.goal}"
        )

    async def _handle_hype_train_progress(self, event_type: str, payload):
        """Handle HypeTrainProgress payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "progress": payload.progress,
            "goal": payload.goal,
            "level": payload.level,
            "started_at": payload.started_at.isoformat(),
            "expires_at": payload.expires_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed HypeTrainProgress. level={payload.level} progress={payload.progress} goal={payload.goal}"
        )

    async def _handle_hype_train_end(self, event_type: str, payload):
        """Handle HypeTrainEnd payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "total": payload.total,
            "level": payload.level,
            "started_at": payload.started_at.isoformat(),
            "ended_at": payload.ended_at.isoformat(),
            "cooldown_until": payload.cooldown_until.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed HypeTrainEnd. level={payload.level} total={payload.total}"
        )

    async def _handle_goal_begin(self, event_type: str, payload):
        """Handle GoalBegin payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "type": payload.type,
            "description": payload.description,
            "current_amount": payload.current_amount,
            "target_amount": payload.target_amount,
            "started_at": payload.started_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed GoalBegin. type={payload.type} description="{payload.description}" progress={payload.current_amount}/{payload.target_amount}'
        )

    async def _handle_goal_progress(self, event_type: str, payload):
        """Handle GoalProgress payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "type": payload.type,
            "description": payload.description,
            "current_amount": payload.current_amount,
            "target_amount": payload.target_amount,
            "started_at": payload.started_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f'[TwitchIO] Processed GoalProgress. type={payload.type} description="{payload.description}" progress={payload.current_amount}/{payload.target_amount}'
        )

    async def _handle_goal_end(self, event_type: str, payload):
        """Handle GoalEnd payload."""
        payload_dict = {
            "id": payload.id,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "type": payload.type,
            "description": payload.description,
            "is_achieved": payload.is_achieved,
            "current_amount": payload.current_amount,
            "target_amount": payload.target_amount,
            "started_at": payload.started_at.isoformat(),
            "ended_at": payload.ended_at.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        status = "achieved" if payload.is_achieved else "ended"
        logger.info(
            f'[TwitchIO] Processed GoalEnd. type={payload.type} description="{payload.description}" status={status} progress={payload.current_amount}/{payload.target_amount}'
        )

    async def _handle_ad_break_begin(self, event_type: str, payload):
        """Handle ChannelAdBreakBegin payload."""
        payload_dict = {
            "duration_seconds": payload.duration,
            "started_at": payload.started_at.isoformat(),
            "is_automatic": payload.automatic,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "requester_user_id": payload.requester.id,
            "requester_user_name": payload.requester.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        ad_type = (
            "automatic" if payload.automatic else f"manual by {payload.requester.name}"
        )
        logger.info(
            f"[TwitchIO] Processed ChannelAdBreakBegin. duration={payload.duration}s type={ad_type}"
        )

    async def _handle_vip_add(self, event_type: str, payload):
        """Handle ChannelVIPAdd payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(f"[TwitchIO] Processed ChannelVIPAdd. user={payload.user.name}")

    async def _handle_vip_remove(self, event_type: str, payload):
        """Handle ChannelVIPRemove payload."""
        payload_dict = {
            "user_id": payload.user.id,
            "user_name": payload.user.name,
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(f"[TwitchIO] Processed ChannelVIPRemove. user={payload.user.name}")

    async def _handle_shoutout_create(self, event_type: str, payload):
        """Handle ShoutoutCreate payload."""
        payload_dict = {
            "broadcaster_user_id": payload.broadcaster.id,
            "broadcaster_user_name": payload.broadcaster.name,
            "to_broadcaster_user_id": payload.to_broadcaster.id,
            "to_broadcaster_user_name": payload.to_broadcaster.name,
            "moderator_user_id": payload.moderator.id,
            "moderator_user_name": payload.moderator.name,
            "viewer_count": payload.viewer_count,
            "started_at": payload.started_at.isoformat(),
            "cooldown_until": payload.cooldown_until.isoformat(),
            "target_cooldown_until": payload.target_cooldown_until.isoformat(),
        }
        member = await self._get_or_create_member_from_payload(payload)
        event = await self._create_event(event_type, payload_dict, member)
        await self._publish_to_redis(event_type, event, member, payload_dict)
        logger.info(
            f"[TwitchIO] Processed ShoutoutCreate. from={payload.broadcaster.name} to={payload.to_broadcaster.name} viewers={payload.viewer_count}"
        )

    async def _handle_limit_break_update(self, payload):
        """Handle limit break updates when 'Throw Something At Me' reward events occur."""
        # The reward ID for "Throw Something At Me"
        THROW_REWARD_ID = "5685d03e-80c2-4640-ba06-566fb8bbc4ce"

        # Check if this event is for our target reward
        if payload.reward.id != THROW_REWARD_ID:
            return  # Not the reward we care about

        logger.info(
            f"[FFBot] 🎮 Limit Break: Processing redemption. user={payload.user.name} status={payload.status}"
        )

        try:
            # Track count locally to avoid constant API calls
            count = 0

            # Check if it's time for a periodic sync (every 45 seconds)
            last_sync = await self._redis_client.get("limitbreak:last_api_sync")
            current_time = timezone.now().timestamp()
            should_sync = not last_sync or (current_time - float(last_sync)) > 45

            # For new redemptions, increment our local count
            if payload.status == "unfulfilled":
                # Get current cached count
                cached_count = await self._redis_client.get("limitbreak:local_count")
                if cached_count:
                    count = int(cached_count) + 1
                    await self._redis_client.set(
                        "limitbreak:local_count", str(count), ex=300
                    )
                    logger.info(
                        f"[FFBot] 🎮 Limit Break: Incremented local count. count={count}"
                    )

                    # Periodic sync to ensure accuracy
                    if should_sync:
                        from shared.services.twitch.helix import helix_service

                        api_count = await helix_service.get_reward_redemption_count(
                            THROW_REWARD_ID
                        )
                        if abs(api_count - count) > 2:  # If drift is significant
                            logger.warning(
                                f"[FFBot] 🟡 Limit Break: Count drift detected. local={count} api={api_count}"
                            )
                            count = api_count
                            await self._redis_client.set(
                                "limitbreak:local_count", str(count), ex=300
                            )
                        await self._redis_client.set(
                            "limitbreak:last_api_sync", str(current_time), ex=60
                        )
                        logger.info(
                            f"[FFBot] 🎮 Limit Break: Periodic sync complete. count={count}"
                        )
                else:
                    # No cached count, need initial sync with API
                    from shared.services.twitch.helix import helix_service

                    count = await helix_service.get_reward_redemption_count(
                        THROW_REWARD_ID
                    )
                    await self._redis_client.set(
                        "limitbreak:local_count", str(count), ex=300
                    )
                    await self._redis_client.set(
                        "limitbreak:last_api_sync", str(current_time), ex=60
                    )
                    logger.info(
                        f"[FFBot] 🎮 Limit Break: Initial sync with API. count={count}"
                    )

            # For fulfilled redemptions, check if we need to sync or handle execution
            elif payload.status == "fulfilled":
                # Get current cached count
                cached_count = await self._redis_client.get("limitbreak:local_count")
                if cached_count:
                    previous_cached = int(cached_count)
                    count = max(0, previous_cached - 1)  # Decrement for fulfilled
                    await self._redis_client.set(
                        "limitbreak:local_count", str(count), ex=300
                    )
                    logger.info(
                        f"[FFBot] 🎮 Limit Break: Decremented count. previous={previous_cached} current={count}"
                    )

                    # Periodic sync to ensure accuracy (same 45 second interval)
                    if should_sync:
                        from shared.services.twitch.helix import helix_service

                        api_count = await helix_service.get_reward_redemption_count(
                            THROW_REWARD_ID
                        )
                        if abs(api_count - count) > 2:  # If drift is significant
                            logger.warning(
                                f"[FFBot] 🟡 Limit Break: Count drift detected (fulfilled). local={count} api={api_count}"
                            )
                            count = api_count
                            await self._redis_client.set(
                                "limitbreak:local_count", str(count), ex=300
                            )
                        await self._redis_client.set(
                            "limitbreak:last_api_sync", str(current_time), ex=60
                        )
                        logger.info(
                            f"[FFBot] 🎮 Limit Break: Periodic sync complete (fulfilled). count={count}"
                        )
                else:
                    # Need initial sync with API
                    from shared.services.twitch.helix import helix_service

                    count = await helix_service.get_reward_redemption_count(
                        THROW_REWARD_ID
                    )
                    await self._redis_client.set(
                        "limitbreak:local_count", str(count), ex=300
                    )
                    await self._redis_client.set(
                        "limitbreak:last_api_sync", str(current_time), ex=60
                    )
                    logger.info(
                        f"[FFBot] 🎮 Limit Break: Initial sync with API (fulfilled). count={count}"
                    )

            logger.info(f"[FFBot] 🎮 Limit Break: Current queue count. count={count}")

            # Check for limit break execution (bulk fulfillment)
            # Detect the FIRST fulfillment when queue was at 100 (maxed)
            if payload.status == "fulfilled":
                # Get the previous count to see if we're coming from a maxed state
                previous_count_str = await self._redis_client.get(
                    "limitbreak:previous_count"
                )
                previous_count = int(previous_count_str) if previous_count_str else 0

                logger.info(
                    f"[FFBot] 🎮 Limit Break: Count comparison. previous={previous_count} current={count}"
                )

                # If previous count was maxed (100+) and we're getting fulfillments,
                # this is the start of the limit break execution
                if previous_count >= 100:
                    # Check if we've already sent an execution event recently
                    last_execution = await self._redis_client.get(
                        "limitbreak:last_execution"
                    )
                    current_time = timezone.now().timestamp()

                    # 60 second window - no way chat rebuilds to 100 that fast
                    if (
                        not last_execution
                        or (current_time - float(last_execution)) > 60
                    ):
                        # Send limit break execution event immediately on first fulfillment
                        await self._redis_client.publish(
                            "events:limitbreak",
                            json.dumps(
                                {
                                    "event_type": "limitbreak.executed",
                                    "data": {
                                        "previous_count": previous_count,
                                        "current_count": count,
                                    },
                                    "timestamp": timezone.now().isoformat(),
                                }
                            ),
                        )
                        # Store execution timestamp with 60 second TTL
                        await self._redis_client.set(
                            "limitbreak:last_execution", str(current_time), ex=60
                        )

                        # Clear the cache since we know redemptions are being fulfilled
                        cache_key = f"limitbreak:count:{THROW_REWARD_ID}"
                        await self._redis_client.set(cache_key, "0", ex=30)
                        await self._redis_client.set(
                            f"{cache_key}:fallback", "0", ex=3600
                        )
                        # Also clear the local count
                        await self._redis_client.set(
                            "limitbreak:local_count", "0", ex=300
                        )

                        logger.info(
                            f"[FFBot] 🎮 Limit Break: EXECUTED! Detected bulk fulfillment. previous={previous_count}"
                        )

                        # Immediately send a sync event with count=0 to update the overlay
                        reset_data = {
                            "count": 0,
                            "bar1": 0.0,
                            "bar2": 0.0,
                            "bar3": 0.0,
                            "isMaxed": False,
                        }
                        await self._redis_client.publish(
                            "events:limitbreak",
                            json.dumps(
                                {
                                    "event_type": "limitbreak.sync",
                                    "data": reset_data,
                                    "timestamp": timezone.now().isoformat(),
                                }
                            ),
                        )
                        logger.info("[FFBot] 🎮 Limit Break: Sent reset sync. count=0")

            # Store current count for next comparison (with 5 minute TTL)
            await self._redis_client.set(
                "limitbreak:previous_count", str(count), ex=300
            )

            # Calculate limit break state (3 bars: 33/66/100)
            bar1_fill = min(count / 33, 1.0)
            bar2_fill = min(max(count - 33, 0) / 33, 1.0) if count > 33 else 0
            bar3_fill = min(max(count - 66, 0) / 34, 1.0) if count > 66 else 0
            is_maxed = count >= 100

            limit_break_data = {
                "count": count,
                "bar1": bar1_fill,
                "bar2": bar2_fill,
                "bar3": bar3_fill,
                "isMaxed": is_maxed,
            }

            logger.info(f"[FFBot] 🎮 Limit Break: Publishing update. count={count}")

            # Publish to Redis for overlay consumers
            await self._redis_client.publish(
                "events:limitbreak",
                json.dumps(
                    {
                        "event_type": "limitbreak.update",
                        "data": limit_break_data,
                        "timestamp": timezone.now().isoformat(),
                    }
                ),
            )

            logger.info(
                f"[FFBot] 🎮 Limit Break: Update published. count={count} bars={bar1_fill:.2f}/{bar2_fill:.2f}/{bar3_fill:.2f} maxed={is_maxed}"
            )

        except Exception as e:
            logger.error(
                f'[FFBot] ❌ Failed to handle limit break update. error="{str(e)}"'
            )

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

            logger.debug(
                f"[TwitchIO] Published event to Redis. event_type={event_type} channel={channel}"
            )

        except Exception as e:
            logger.warning(f'[TwitchIO] Failed to publish to Redis. error="{str(e)}"')

    async def _get_or_create_member_from_payload(self, payload) -> Member | None:
        """Extract Member information from EventSub payload using TwitchIO object-based access."""
        # TwitchIO event payloads have different user attributes based on event type
        # Try each in order of priority, handling None for anonymous events
        user_obj = None

        if hasattr(payload, "user") and payload.user:
            user_obj = payload.user
        elif hasattr(payload, "chatter") and payload.chatter:
            user_obj = payload.chatter
        elif hasattr(payload, "from_broadcaster") and payload.from_broadcaster:
            user_obj = payload.from_broadcaster
        elif hasattr(payload, "broadcaster") and payload.broadcaster:
            user_obj = payload.broadcaster

        if not user_obj:
            return None  # Anonymous event with no user info

        twitch_id = str(user_obj.id)
        username = user_obj.name
        display_name = user_obj.display_name

        # Use update_or_create to avoid race conditions
        defaults = {
            "username": username,
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
                if created:
                    logger.info(f"[Session] Session created. date={stream_date}")
                else:
                    logger.debug(f"[Session] Session found. date={stream_date}")

                # Store session ID in Redis with 12-hour TTL
                redis_key = "twitch:active_session"
                ttl_seconds = 12 * 60 * 60  # 12 hours
                await self._redis_client.set(redis_key, str(session.id), ex=ttl_seconds)
                logger.debug(
                    f"[Session] Stored session in Redis. id={session.id} ttl={ttl_seconds}s"
                )

            except Exception as e:
                logger.error(
                    f'[Session] ❌ Failed to create session. date={stream_date} error="{str(e)}"',
                    exc_info=True,
                )
                session = None
        elif event_type == "stream.offline":
            # Keep the session active for 30 minutes after stream.offline
            # This allows post-stream events (raids, etc.) to be associated with the stream
            # Also handles errant offline events where stream comes back online
            try:
                redis_key = "twitch:active_session"
                session_id = await self._redis_client.get(redis_key)
                if session_id:
                    # Decode session_id from bytes to string
                    session_id_str = (
                        session_id.decode("utf-8")
                        if isinstance(session_id, bytes)
                        else session_id
                    )
                    session = await sync_to_async(
                        Session.objects.filter(id=session_id_str).first
                    )()
                    if session:
                        # Set expiry to 30 minutes from now
                        ttl_seconds = 30 * 60  # 30 minutes
                        await self._redis_client.expire(redis_key, ttl_seconds)
                        logger.debug(
                            f"[Session] Extended session expiry for post-stream events. id={session.id} ttl={ttl_seconds // 60}min"
                        )
                    else:
                        logger.warning(
                            f"[Session] 🟡 Session from Redis not found in database. id={session_id_str}"
                        )
                        session = None
                else:
                    logger.debug("[Session] No active session during stream.offline.")
                    session = None
            except Exception as e:
                logger.error(
                    f'[Session] ❌ Failed to handle session during stream.offline. error="{str(e)}"'
                )
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
                    logger.debug(
                        f"[Session] Using active session from Redis. id={session_id_str}"
                    )
                else:
                    # Redis miss - check database for recent active session
                    logger.debug("[Session] No session in Redis, checking database.")

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
                        logger.debug(
                            f"[Session] Populated Redis with recent session. id={session.id}"
                        )
                    else:
                        logger.debug("[Session] No recent session found in database.")
                        session = None

            except Exception as e:
                logger.error(
                    f'[Session] ❌ Failed to find active session. error="{str(e)}"'
                )
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
                        f"[Session] 🟡 Created fallback session. date={current_date}"
                    )
                else:
                    logger.debug(
                        f"[Session] Using existing session as fallback. date={current_date}"
                    )

                # Store in Redis for future events
                if session:
                    redis_key = "twitch:active_session"
                    ttl_seconds = 12 * 60 * 60  # 12 hours
                    await self._redis_client.set(
                        redis_key, str(session.id), ex=ttl_seconds
                    )
                    logger.debug(
                        f"[Session] Stored fallback session in Redis. id={session.id}"
                    )

            except Exception as e:
                logger.error(
                    f'[Session] ❌ Failed to create fallback session. error="{str(e)}"'
                )
                session = None

        return await sync_to_async(Event.objects.create)(
            source="twitch",
            event_type=event_type,
            member=member,
            session=session,
            payload=payload,
            timestamp=timezone.now(),
        )
