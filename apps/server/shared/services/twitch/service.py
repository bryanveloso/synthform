"""Lean TwitchIO adapter service for OAuth and EventSub routing."""

from __future__ import annotations

import asyncio
import logging
import os

# Setup Django for standalone execution
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")

import django

django.setup()

import twitchio  # noqa: E402
from django.conf import settings  # noqa: E402
from twitchio import eventsub  # noqa: E402
from twitchio.exceptions import HTTPException  # noqa: E402
from twitchio.exceptions import InvalidTokenException  # noqa: E402
from twitchio.web.starlette_adapter import StarletteAdapter  # noqa: E402

from authentication.services import AuthService  # noqa: E402
from events.services.twitch import TwitchEventHandler  # noqa: E402

logger = logging.getLogger(__name__)

# Configure TwitchIO logging to reduce noise
logging.getLogger("twitchio.authentication.tokens").setLevel(logging.WARNING)
logging.getLogger("twitchio.eventsub.websockets").setLevel(logging.WARNING)


class TwitchService(twitchio.Client):
    """Lean TwitchIO adapter for OAuth callbacks and EventSub delegation."""

    def __init__(self):
        """Initialize TwitchIO client with StarletteAdapter."""
        super().__init__(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            adapter=StarletteAdapter(
                domain=settings.EVENTSUB_DOMAIN,
                host="0.0.0.0",
                port=4343,
                eventsub_secret=settings.TWITCH_EVENTSUB_SECRET,
            ),
        )
        self._eventsub_connected = False
        self._event_handler = TwitchEventHandler()
        self._auth_service = AuthService("twitch")
        logger.info("TwitchIO adapter service initialized")

    async def event_ready(self):
        """Called when the client is ready."""
        logger.info("TwitchIO client ready")

        # Load existing tokens from database
        await self._load_existing_tokens()

        # Subscribe to EventSub events
        await self._subscribe_to_events()

        self._eventsub_connected = True
        logger.info("EventSub connection established and subscriptions created")

    async def event_oauth_authorized(
        self, payload: twitchio.OAuthAuthorizedPayload
    ) -> twitchio.ResponsePayload | None:
        """Handle OAuth authorization callbacks."""
        logger.info(f"OAuth authorized for user: {payload.user_id}")

        try:
            # Save token to database through auth service
            await self._auth_service.save_token(
                user_id=payload.user_id,
                access_token=payload.access_token,
                refresh_token=payload.refresh_token,
                expires_in=payload.expires_in,
            )

            # Subscribe to events for this user
            await self._subscribe_to_events_for_user(payload.user_id)

            return twitchio.ResponsePayload(
                status=200,
                title="Authorization Successful",
                message="Your Twitch account has been connected successfully!",
            )
        except Exception as e:
            logger.error(f"Error in OAuth authorization: {e}")
            return twitchio.ResponsePayload(
                status=500,
                title="Authorization Failed",
                message=f"Failed to save authorization: {str(e)}",
            )

    async def event_token_refreshed(self, payload: twitchio.TokenRefreshedPayload):
        """Handle token refresh events."""
        logger.info(f"Token refreshed for user: {payload.user_id}")

        try:
            # Update token in database through auth service
            await self._auth_service.update_token(
                user_id=payload.user_id,
                access_token=payload.token,
                refresh_token=payload.refresh_token,
                expires_in=payload.expires_in,
            )
        except Exception as e:
            logger.error(f"Error updating refreshed token: {e}")

    async def add_token(
        self,
        access_token,
        refresh_token=None,
        user_id=None,
        scopes=None,
        expires_at=None,
    ):
        """Override TwitchIO's add_token method to store in database."""
        # First call the parent method to maintain TwitchIO functionality
        result = await super().add_token(access_token, refresh_token)

        # Extract user_id using TwitchIO's fetch_users method if needed
        if not user_id:
            try:
                # Use TwitchIO's fetch_users to get current user info from the token
                users = await self.fetch_users()
                if users:
                    user_id = str(users[0].id)
                    # TwitchIO doesn't expose scopes/expires_at easily,
                    # so we'll rely on defaults for now
            except InvalidTokenException as token_error:
                logger.error(
                    f"Invalid token when fetching user for add_token: {token_error}"
                )
                return result
            except HTTPException as http_error:
                logger.error(f"HTTP error fetching user for add_token: {http_error}")
                return result
            except Exception as e:
                logger.error(f"Unexpected error fetching user info using TwitchIO: {e}")
                return result

        # Save to database
        if user_id:
            # Save token using AuthService
            await self._auth_service.save_token(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600,  # Default expires_in
            )

        return result

    async def _load_existing_tokens(self):
        """Load existing tokens from database on startup."""
        try:
            tokens = await self._auth_service.get_all_tokens()

            valid_tokens = []
            for token_data in tokens:
                logger.info(f"Loading token for user: {token_data['user_id']}")
                try:
                    # Call parent's add_token method directly - only takes access and refresh
                    await super().add_token(
                        token_data["access_token"], token_data["refresh_token"]
                    )
                    valid_tokens.append(token_data)
                    logger.info(
                        f"Loaded token for user {token_data['user_id']} from database"
                    )
                except Exception as e:
                    logger.error(
                        f"Error loading token for user {token_data['user_id']}: {e}"
                    )

            # If we have valid tokens, automatically subscribe to events
            if valid_tokens:
                primary_token = valid_tokens[0]  # Use first valid token
                logger.info(
                    f"Subscribing to EventSub events for user {primary_token['user_id']}"
                )
                await self._subscribe_to_events_for_user(str(primary_token["user_id"]))

            if tokens:
                logger.info(f"Loaded {len(valid_tokens)} valid tokens from database")
            else:
                logger.info("No existing tokens found")

        except Exception as e:
            logger.error(f"Error loading existing tokens: {e}")

    async def _subscribe_to_events(self):
        """Subscribe to EventSub events for authenticated users."""
        try:
            # This method is called after event_ready, check if we have a user
            if not self.user:
                logger.debug(
                    "No user context in client - subscriptions handled via loaded tokens"
                )
                return

            user_id = str(self.user.id)
            await self._subscribe_to_events_for_user(user_id)

        except Exception as e:
            logger.error(f"Error subscribing to events: {e}")

    async def _subscribe_to_events_for_user(self, user_id: str):
        """Subscribe to Twitch EventSub events for a specific user ID using subscription payload objects."""
        try:
            # Create subscription payload objects with the correct conditions
            subscriptions = [
                # Stream events
                eventsub.StreamOnlineSubscription(broadcaster_user_id=user_id),
                eventsub.StreamOfflineSubscription(broadcaster_user_id=user_id),
                # Channel information updates
                eventsub.ChannelUpdateSubscription(broadcaster_user_id=user_id),
                # Follow events
                eventsub.ChannelFollowSubscription(
                    broadcaster_user_id=user_id, moderator_user_id=user_id
                ),
                # Subscription events
                eventsub.ChannelSubscribeSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelSubscriptionEndSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelSubscriptionGiftSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelSubscribeMessageSubscription(
                    broadcaster_user_id=user_id
                ),
                # Bits/Cheer events
                eventsub.ChannelCheerSubscription(broadcaster_user_id=user_id),
                # Raid events
                eventsub.ChannelRaidSubscription(to_broadcaster_user_id=user_id),
                # Chat events
                eventsub.ChatClearSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatClearUserMessagesSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatMessageSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatNotificationSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                # Channel Points events
                eventsub.ChannelPointsRewardAddSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRewardUpdateSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRewardRemoveSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRedeemAddSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRedeemUpdateSubscription(
                    broadcaster_user_id=user_id
                ),
                # Poll events
                eventsub.ChannelPollBeginSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPollProgressSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPollEndSubscription(broadcaster_user_id=user_id),
                # Prediction events
                eventsub.ChannelPredictionBeginSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPredictionProgressSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPredictionLockSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPredictionEndSubscription(broadcaster_user_id=user_id),
                # Charity events
                eventsub.CharityDonationSubscription(broadcaster_user_id=user_id),
                # Hype Train events
                eventsub.HypeTrainBeginSubscription(broadcaster_user_id=user_id),
                eventsub.HypeTrainProgressSubscription(broadcaster_user_id=user_id),
                eventsub.HypeTrainEndSubscription(broadcaster_user_id=user_id),
                # Goal events
                eventsub.GoalBeginSubscription(broadcaster_user_id=user_id),
                eventsub.GoalProgressSubscription(broadcaster_user_id=user_id),
                eventsub.GoalEndSubscription(broadcaster_user_id=user_id),
                # Shoutout events
                eventsub.ShoutoutCreateSubscription(
                    broadcaster_user_id=user_id, moderator_user_id=user_id
                ),
                # VIP events
                eventsub.ChannelVIPAddSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelVIPRemoveSubscription(broadcaster_user_id=user_id),
                # Ad break events
                eventsub.AdBreakBeginSubscription(broadcaster_user_id=user_id),
            ]

            for subscription in subscriptions:
                try:
                    await self.subscribe_websocket(subscription, token_for=user_id)
                    logger.info(
                        f"Successfully subscribed to {subscription.__class__.__name__}"
                    )
                except InvalidTokenException as token_error:
                    logger.error(
                        f"Invalid token when subscribing to {subscription.__class__.__name__}: {token_error}"
                    )
                except HTTPException as http_error:
                    logger.error(
                        f"HTTP error subscribing to {subscription.__class__.__name__}: {http_error}"
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error subscribing to {subscription.__class__.__name__}: {e}"
                    )

            self._eventsub_connected = True

        except Exception as e:
            logger.error(f"Error subscribing to events for user {user_id}: {e}")

    async def _safe_delegate(self, handler_method, payload, event_name: str):
        """Safely delegate events to handler with error handling."""
        try:
            await handler_method(payload)
        except AttributeError as e:
            logger.error(f"Handler method not found for {event_name}: {e}")
        except Exception as e:
            logger.error(f"Error handling {event_name} event: {e}", exc_info=True)
            # Don't re-raise to prevent breaking the event loop

    # EventSub event delegation methods with error handling
    async def event_follow(self, payload):
        """Delegate follow events to handler."""
        await self._safe_delegate(self._event_handler.event_follow, payload, "follow")

    async def event_subscription(self, payload):
        """Delegate subscription events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription, payload, "subscription"
        )

    async def event_subscription_gift(self, payload):
        """Delegate subscription gift events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_gift, payload, "subscription_gift"
        )

    async def event_subscription_message(self, payload):
        """Delegate subscription message events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_message,
            payload,
            "subscription_message",
        )

    async def event_cheer(self, payload):
        """Delegate cheer events to handler."""
        await self._safe_delegate(self._event_handler.event_cheer, payload, "cheer")

    async def event_raid(self, payload):
        """Delegate raid events to handler."""
        await self._safe_delegate(self._event_handler.event_raid, payload, "raid")

    async def event_ban(self, payload):
        """Delegate ban events to handler."""
        await self._safe_delegate(self._event_handler.event_ban, payload, "ban")

    async def event_unban(self, payload):
        """Delegate unban events to handler."""
        await self._safe_delegate(self._event_handler.event_unban, payload, "unban")

    async def event_stream_online(self, payload):
        """Delegate stream online events to handler."""
        await self._safe_delegate(
            self._event_handler.event_stream_online, payload, "stream_online"
        )

    async def event_stream_offline(self, payload):
        """Delegate stream offline events to handler."""
        await self._safe_delegate(
            self._event_handler.event_stream_offline, payload, "stream_offline"
        )

    async def event_channel_update(self, payload):
        """Delegate channel update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_channel_update, payload, "channel_update"
        )

    async def event_subscription_end(self, payload):
        """Delegate subscription end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_end, payload, "subscription_end"
        )

    # Chat event delegation methods
    async def event_message(self, payload):
        """Delegate chat message events to handler."""
        await self._safe_delegate(
            self._event_handler.event_message, payload, "chat_message"
        )

    async def event_message_delete(self, payload):
        """Delegate message delete events to handler."""
        await self._safe_delegate(
            self._event_handler.event_message_delete,
            payload,
            "chat_message_delete",
        )

    async def event_chat_notification(self, payload):
        """Delegate chat notification events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_notification, payload, "chat_notification"
        )

    async def event_chat_clear(self, payload):
        """Delegate chat clear events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_clear, payload, "chat_clear"
        )

    async def event_chat_clear_user(self, payload):
        """Delegate chat clear user events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_clear_user, payload, "chat_clear_user"
        )

    # Channel Points event delegation
    async def event_custom_reward_add(self, payload):
        """Delegate custom reward add events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_add, payload, "custom_reward_add"
        )

    async def event_custom_reward_update(self, payload):
        """Delegate custom reward update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_update,
            payload,
            "custom_reward_update",
        )

    async def event_custom_reward_remove(self, payload):
        """Delegate custom reward remove events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_remove,
            payload,
            "custom_reward_remove",
        )

    async def event_custom_redemption_add(self, payload):
        """Delegate custom redemption add events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_redemption_add,
            payload,
            "custom_redemption_add",
        )

    async def event_custom_redemption_update(self, payload):
        """Delegate custom redemption update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_redemption_update,
            payload,
            "custom_redemption_update",
        )

    # Poll event delegation
    async def event_poll_begin(self, payload):
        """Delegate poll begin events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_poll_begin, payload, "poll_begin"
        )

    async def event_poll_progress(self, payload):
        """Delegate poll progress events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_poll_progress, payload, "poll_progress"
        )

    async def event_poll_end(self, payload):
        """Delegate poll end events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_poll_end, payload, "poll_end"
        )

    # Prediction event delegation
    async def event_prediction_begin(self, payload):
        """Delegate prediction begin events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_prediction_begin, payload, "prediction_begin"
        )

    async def event_prediction_progress(self, payload):
        """Delegate prediction progress events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_prediction_progress,
            payload,
            "prediction_progress",
        )

    async def event_prediction_lock(self, payload):
        """Delegate prediction lock events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_prediction_lock, payload, "prediction_lock"
        )

    async def event_prediction_end(self, payload):
        """Delegate prediction end events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_prediction_end, payload, "prediction_end"
        )

    # Hype Train event delegation
    async def event_hype_train(self, payload):
        """Delegate hype train begin events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_hype_train_begin, payload, "hype_train_begin"
        )

    async def event_hype_train_progress(self, payload):
        """Delegate hype train progress events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_hype_train_progress,
            payload,
            "hype_train_progress",
        )

    async def event_hype_train_end(self, payload):
        """Delegate hype train end events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_hype_train_end, payload, "hype_train_end"
        )

    # Goal event delegation
    async def event_goal_begin(self, payload):
        """Delegate goal begin events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_goal_begin, payload, "goal_begin"
        )

    async def event_goal_progress(self, payload):
        """Delegate goal progress events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_goal_progress, payload, "goal_progress"
        )

    async def event_goal_end(self, payload):
        """Delegate goal end events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_goal_end, payload, "goal_end"
        )

    # Charity event delegation
    async def event_charity_campaign_donate(self, payload):
        """Delegate charity donation events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_charity_donation, payload, "charity_donation"
        )

    # Shoutout event delegation
    async def event_shoutout_create(self, payload):
        """Delegate shoutout create events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_shoutout_create, payload, "shoutout_create"
        )

    async def event_shoutout_receive(self, payload):
        """Delegate shoutout receive events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_shoutout_receive, payload, "shoutout_receive"
        )

    # VIP event delegation
    async def event_vip_add(self, payload):
        """Delegate VIP add events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_vip_add, payload, "vip_add"
        )

    async def event_vip_remove(self, payload):
        """Delegate VIP remove events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_vip_remove, payload, "vip_remove"
        )

    # Ad break event delegation
    async def event_ad_break(self, payload):
        """Delegate ad break events to handler."""
        await self._safe_delegate(
            self._event_handler.handle_ad_break, payload, "ad_break"
        )


async def main():
    """Run the TwitchIO adapter service."""
    service = TwitchService()

    try:
        logger.info("Starting TwitchIO adapter service on port 4343")
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        await service.close()
        logger.info("TwitchIO adapter service stopped")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Enable TwitchIO debugging
    logging.getLogger("twitchio").setLevel(logging.DEBUG)
    logging.getLogger("twitchio.web").setLevel(logging.DEBUG)

    # Run the service
    asyncio.run(main())
