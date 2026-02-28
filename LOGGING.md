# Synthform Logging Standard

This document defines the logging standard for the Synthform streaming overlay system. All new logs must follow this standard, and existing logs should be migrated incrementally.

## Overview

Logs are consumed directly via `docker compose logs -f` by a single developer for real-time debugging during streams. The standard prioritizes:
- **Human readability** - No JSON or structured logging formats
- **Scannability** - Consistent format for quick visual parsing
- **Information density** - Preserve critical debugging details
- **Consistency** - Predictable structure across all services

## Format Specification

```
[Component] Message. [key=value key2="value with spaces"]
```

**Components:**
- `[Component]` - Service or module name (e.g., `[OBS]`, `[TwitchIO]`, `[Redis]`)
- `Message` - Human-readable description of the event
- `[key=value ...]` - Optional structured context for filtering/searching

## Rules

### 1. Tense

- **Past tense** for completed actions: "Connected", "Started", "Processed", "Refreshed"
- **Present tense** for ongoing states (rare): "Connecting", "Retrying"
- **Never use progressive with ellipses**: ~~"Starting..."~~ → "Started"

### 2. Component Identification

Always include the component/service name in brackets:
- `[OBS]` - OBS WebSocket service
- `[TwitchIO]` - TwitchIO EventSub service
- `[Redis]` - Redis connections
- `[WebSocket]` - WebSocket consumer/overlay clients
- `[Rainwave]` - Rainwave music service
- `[RME]` - RME TotalMix audio service
- `[Campaign]` - Campaign/milestone system
- `[FFBot]` - FFBot game integration

### 3. Structured Context

Use `key=value` format at the end of the line:
- Simple values: `version=1.2.3 port=4455 count=11`
- Values with spaces: `error="Connection refused" reason="Token expired"`
- Always lowercase keys
- Use underscores for multi-word keys: `user_id=123 client_id=abc`

### 4. Emojis (Minimal)

Use emojis sparingly as visual anchors for critical events:

- ✅ **Major successes** - Reconnections, critical completions, deployment success
- ❌ **Critical errors** - System failures, connection losses
- 🟡 **Warnings** - Issues requiring attention but not failing
- 🎵 **Music/audio** - Music playback events, audio state changes
- 🎮 **Game** - Game-related events (FFBot, etc.)
- 💾 **Persistence** - Save operations, database writes

**NO emojis for:**
- Routine operations (starting services, processing events)
- Debug logs
- Informational messages

### 5. Punctuation

- **Always end with period** for complete thoughts
- **Use colon** for introducing details: `Failed to connect: Connection refused`
- **No ellipses** except for actual continuation (rare)

### 6. Detail Preservation

Always include:
- **Version numbers** for external connections: `version=32.0.0`
- **IDs** for clients/sessions: `id=abc123 session_id=xyz789`
- **Counts** for batch operations: `count=11 processed=150`
- **Error context** - Never bare "Error", always include reason

## Examples

### Service Lifecycle

```python
# ❌ Before
logger.info("🚀 Starting background services...")
logger.info("Starting OBS service...")
logger.info("Auto-starting OBS service...")

# ✅ After
logger.info("[EventsConfig] Background services started.")
logger.info("[OBS] Service started.")
```

### External Connections

```python
# ❌ Before
logger.info(f"Connected to OBS Studio {version.obs_version}")
logger.info("Successfully identified ReqClient with the server using RPC version:1")

# ✅ After
logger.info(f"[OBS] Connected to OBS Studio. version={version.obs_version}")
logger.info("[OBS] ReqClient identified. rpc_version=1")
```

### Client Connections

```python
# ❌ Before
logger.info("Overlay client connected")
logger.info(f"Overlay client connected [ID: {client_id}]")
logger.info(f"Overlay client disconnected with code: {close_code}")

# ✅ After
logger.info(f"[WebSocket] Overlay client connected. id={client_id}")
logger.info(f"[WebSocket] Overlay client disconnected. code={close_code}")
```

### State Changes

```python
# ❌ Before
logger.info("Redis connection verified")
logger.info("TwitchIO client ready")
logger.info("EventSub connection established and subscriptions created")

# ✅ After
logger.info("[Redis] Connected to Redis.")
logger.info("[TwitchIO] Client initialized.")
logger.info("[TwitchIO] EventSub connected and subscribed.")
```

### Critical Events

```python
# ❌ Before
logger.info("✅ EventSub reconnection successful")
logger.warning(f"EventSub WebSocket disconnected: {payload}")

# ✅ After
logger.info("[TwitchIO] ✅ EventSub reconnected.")
logger.warning(f"[TwitchIO] EventSub disconnected. reason={payload}")
```

### Event Processing

```python
# ❌ Before
logger.info(f"Processed ChannelFollow: {payload.user.display_name} followed")
logger.info(f"Processed ChannelCheer: {payload.bits} bits from {user_name}")

# ✅ After
logger.info(f"[TwitchIO] Processed ChannelFollow. user={payload.user.display_name}")
logger.info(f"[TwitchIO] Processed ChannelCheer. user={user_name} bits={payload.bits}")
```

### Batch Operations

```python
# ❌ Before
logger.info(f"Refreshed browser source: {source_name}")
logger.info(f"Refreshed {len(browser_sources)} browser sources")

# ✅ After
logger.info(f"[OBS] Refreshed browser source. name={source_name}")
logger.info(f"[OBS] Refreshed browser sources. count={len(browser_sources)}")
```

### Errors

```python
# ❌ Before
logger.error(f"Failed to connect to OBS: {e}")
logger.error(f"Error saving token for {self.service_name}:{user_id}: {e}")

# ✅ After
logger.error(f"[OBS] Failed to connect. error=\"{str(e)}\"")
logger.error(f"[Auth] Failed to save token. service={self.service_name} user_id={user_id} error=\"{str(e)}\"")
```

## Edge Cases

### Stack Traces

The first line should follow the standard. The stack trace follows naturally:

```python
try:
    # ... operation
except Exception as e:
    logger.error(f"[Component] Operation failed. error=\"{str(e)}\"", exc_info=True)
    # Stack trace will be printed automatically by exc_info=True
```

### High-Frequency Events

For events in loops, use `DEBUG` level inside the loop and summarize with `INFO`:

```python
logger.info(f"[AssetProcessor] Started processing assets. count={len(assets)}")
for asset in assets:
    logger.debug(f"[AssetProcessor] Processing asset. id={asset.id}")
    # ... process
logger.info(f"[AssetProcessor] Finished processing assets. processed={processed} failed={failed}")
```

### Multi-line Details

Keep the main message on one line. Use structured context for details:

```python
# ✅ Good
logger.info(f"[Campaign] Milestone unlocked. id={milestone.id} title=\"{milestone.title}\" points={milestone.points}")

# ❌ Avoid
logger.info(f"[Campaign] Milestone unlocked:\n  ID: {milestone.id}\n  Title: {milestone.title}")
```

## Implementation Guidance

### Priority Order

1. **Critical Path** (highest impact on debugging)
   - TwitchIO EventSub connection/reconnection
   - OBS connection/disconnection
   - Redis connection
   - WebSocket client connections

2. **User-Visible Events**
   - Twitch event processing (follows, cheers, raids)
   - Campaign milestones
   - Alert processing

3. **Background Services**
   - Rainwave, RME audio, health checks

4. **Internal/Debug**
   - Debug-level logs, admin commands

### Migration Strategy

- Update logs file-by-file in priority order
- Test after each file to ensure no regressions
- Run the application and check Docker logs for consistency
- Update this document if patterns emerge that aren't covered

## Files to Update

- `events/apps.py` - Background service startup
- `streams/services/obs.py` - OBS connection/events
- `shared/services/twitch/service.py` - TwitchIO EventSub
- `events/services/twitch.py` - Event processing
- `events/consumers.py` - WebSocket connections
- `events/services/rainwave.py` - Rainwave service
- `audio/services/rme.py` - Audio service
- `synthform/health.py` - Health checks
- `authentication/services.py` - Token management
- `shared/services/twitch/helix.py` - Helix API
- `campaigns/*` - Campaign system
- `games/ffbot/*` - FFBot integration
