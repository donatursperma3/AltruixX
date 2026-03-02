# Hater Detector Fix - Requirements

## Overview
Perbaikan plugin xdetect_haters.py yang tidak merespon saat user hater (yang sudah block userbot) mention/reply ke userbot dalam group chat. Plugin harus cocok dengan ecosystem Altruix multiclient.

## Problem Statement
Plugin hater detector tidak berfungsi dengan benar:
- Handler triggered tapi tidak ada response
- Log menunjukkan message tidak terdeteksi sebagai mention
- Tidak cocok dengan multiclient environment Altruix
- Manual mention detection prone to errors

## User Stories

### US-1: Detect Mentions from Blocked Users
**As a** userbot owner  
**I want** plugin to detect when blocked users mention me in groups  
**So that** I can respond automatically to expose their behavior

**Acceptance Criteria:**
- Detects @username mentions
- Detects text mentions (clickable name)
- Detects replies to our messages
- Works in group chats only
- Ignores bot messages
- Ignores service messages

### US-2: Multiclient Compatibility
**As a** Altruix user with multiple userbot sessions  
**I want** hater detector to work correctly with all sessions  
**So that** each session can independently detect haters

**Acceptance Criteria:**
- Works with multiple userbot clients
- No interference between sessions
- Each session detects mentions to itself only
- No false positives from other sessions

### US-3: Reliable Mention Detection
**As a** developer  
**I want** mention detection to use Pyrogram's built-in filters  
**So that** detection is reliable and handles all edge cases

**Acceptance Criteria:**
- Uses `filters.mentioned` built-in from Pyrogram
- No manual entity parsing needed
- Handles all mention types automatically
- More efficient than manual parsing

### US-4: Log Group Protection
**As a** userbot owner  
**I want** plugin to ignore mentions in log group  
**So that** there are no auto-reply loops

**Acceptance Criteria:**
- Detects log group messages
- Skips processing for log group
- Prevents auto-reply loops
- Logs skip action for debugging

### US-5: Block Status Detection
**As a** userbot owner  
**I want** plugin to accurately detect if user blocked me  
**So that** I only respond to actual haters

**Acceptance Criteria:**
- Uses send_chat_action probe to detect blocks
- Caches block status to reduce API calls
- Cache TTL of 5 minutes
- Handles FloodWait gracefully

## Functional Requirements

### FR-1: Filter Configuration
```python
@Altruix.on_message(
    filters.mentioned &      # Built-in mention detection
    filters.group &          # Only groups
    ~filters.bot &           # Ignore bots
    ~filters.service,        # Ignore service messages
    group=3                  # After mention logger (group=0)
)
```

**Requirements:**
- Use `filters.mentioned` instead of `filters.incoming`
- Remove manual mention detection
- Set handler priority to group=3
- Focus on groups only (no channels)

### FR-2: Mention Detection
- Automatically handled by `filters.mentioned`
- No manual entity parsing
- Supports all mention types:
  - @username mentions
  - Text mentions (clickable)
  - Replies to our messages

### FR-3: Log Group Protection
```python
if Altruix.log_chat and message.chat.id == Altruix.log_chat:
    logger.debug(f"[Hater Detector] Ignoring mention in log group")
    return
```

### FR-4: Block Status Detection
```python
async def check_if_blocked(client: Client, user_id: int) -> bool:
    try:
        await client.send_chat_action(user_id, ChatAction.TYPING)
        return False  # Not blocked
    except UserIsBlocked:
        return True   # Blocked
    except PeerIdInvalid:
        return True   # Potential hater
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return False  # Assume not blocked during flood
```

### FR-5: Block Status Caching
```python
BLOCK_STATUS_CACHE = {}  # {user_id: {"blocked": bool, "timestamp": int}}
BLOCK_CACHE_TTL = 300    # 5 minutes

def get_cached_block_status(user_id: int) -> tuple[bool, bool]:
    # Returns: (has_cache, is_blocked)
    
def set_cached_block_status(user_id: int, is_blocked: bool):
    # Cache with timestamp
```

### FR-6: Response System
- Custom response templates with placeholders
- Random or sequential response mode
- Configurable delay before response
- HTML/Markdown parse mode support

### FR-7: Detection Logging
- Log to LOG_CHAT_ID
- Include user info, chat info, detection count
- Configurable (can be disabled)

## Non-Functional Requirements

### NFR-1: Performance
- Minimal CPU usage (no manual parsing)
- Cache block status to reduce API calls
- Early exit if feature disabled
- Early exit if not blocked

### NFR-2: Reliability
- Use Pyrogram's tested filters
- Handle all error cases gracefully
- No crashes on malformed messages
- Defensive programming

### NFR-3: Compatibility
- Works with Altruix multiclient
- Follows xmention_logger_user.py pattern
- No interference with other plugins
- Proper handler priority (group=3)

### NFR-4: Maintainability
- Clean code structure
- Comprehensive logging
- Clear error messages
- Well-documented

## Technical Constraints

- Must use Pyrogram library
- Must integrate with Altruix ecosystem
- Must support multiclient environment
- Must follow existing plugin patterns

## Success Metrics

- Detects all mention types correctly
- No false positives from other sessions
- No auto-reply loops in log group
- Block detection accuracy >95%
- Response time <2 seconds
- Zero crashes

## Dependencies

- Pyrogram library
- Altruix core framework
- iuser_check decorator
- log_errors decorator

## Reference Implementation

Study xmention_logger_user.py pattern:
- Uses `filters.mentioned` built-in
- Removes `filters.incoming` for multiclient
- Adds log group protection
- Proper error handling

## Out of Scope

- Multi-language responses
- Advanced AI responses
- Image/media responses
- Group-specific settings
- User whitelist/blacklist
