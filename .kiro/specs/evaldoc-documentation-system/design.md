# Evaldoc Documentation System - Design

## Architecture Overview

### Component Structure
```
devtools.py
├── Documentation Content (EVAL_DOC_PAGES)
├── Keyboard Generator (get_evaldoc_keyboard)
├── Safe Helper Functions
│   ├── safe_evaldoc_answer()
│   ├── safe_evaldoc_edit()
│   └── safe_evaldoc_delete()
├── Callback Handler (evaldoc_callback_handler)
├── Inline Handler (evaldoc_inline_handler)
└── Command Handler (eval_documentation_handler_inline)
```

## Data Structures

### Documentation Pages
```python
EVAL_DOC_PAGES: List[str] = [
    # 15 pages of documentation
    # Each page: ~200-400 characters
    # Format: HTML with <pre language="python"> for code
]
```

**Page Structure:**
- Header: `<b>📚 Eval & Reval Guide</b>`
- Title: `<b>Page X/15: Topic</b>`
- Content: Mixed text and code blocks
- Footer: Navigation hint `<i>→ .evaldoc X</i>`

### Keyboard Layout
```python
InlineKeyboardMarkup([
    [Prev, Page Indicator, Next],      # Row 1: Navigation
    [First, Client, Last],              # Row 2: Quick Jump
    [Close]                             # Row 3: Close
])
```

## Key Functions

### 1. get_evaldoc_keyboard(page: int)
**Purpose:** Generate inline keyboard for pagination

**Logic:**
```python
def get_evaldoc_keyboard(page: int) -> InlineKeyboardMarkup:
    total_pages = len(EVAL_DOC_PAGES)
    
    # Row 1: Prev | Page X/Total | Next
    row1 = []
    if page > 1:
        row1.append(InlineKeyboardButton("◀️ Prev", callback_data=f"evaldoc_page_{page-1}"))
    else:
        row1.append(InlineKeyboardButton("◀️", callback_data="evaldoc_noop"))
    
    row1.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="evaldoc_noop"))
    
    if page < total_pages:
        row1.append(InlineKeyboardButton("Next ▶️", callback_data=f"evaldoc_page_{page+1}"))
    else:
        row1.append(InlineKeyboardButton("▶️", callback_data="evaldoc_noop"))
    
    # Row 2: First | Client | Last
    row2 = [
        InlineKeyboardButton("⏮️ First", callback_data="evaldoc_page_1"),
        InlineKeyboardButton("⭐ Client", callback_data="evaldoc_page_5"),
        InlineKeyboardButton("Last ⏭️", callback_data=f"evaldoc_page_{total_pages}")
    ]
    
    # Row 3: Close
    row3 = [InlineKeyboardButton("❌ Close", callback_data="evaldoc_close")]
    
    return InlineKeyboardMarkup([row1, row2, row3])
```

**Boundary Handling:**
- Page 1: Prev button disabled (callback = "evaldoc_noop")
- Page 15: Next button disabled (callback = "evaldoc_noop")
- First/Client/Last: Always enabled

### 2. Safe Helper Functions

#### safe_evaldoc_answer()
**Purpose:** Safely answer callback queries without crashing on expired queries

```python
async def safe_evaldoc_answer(cb: CallbackQuery, text: str, show_alert: bool = False):
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass  # Silently ignore expired callbacks
```

#### safe_evaldoc_edit()
**Purpose:** Safely edit messages in both regular and inline mode

```python
async def safe_evaldoc_edit(cb: CallbackQuery, text: str, reply_markup=None):
    try:
        # Uses cb.edit_message_text() - works for both regular and inline
        await cb.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return True
    except Exception as e:
        Altruix.log(f"[evaldoc] Error editing message: {e}", level=40)
        await safe_evaldoc_answer(cb, f"❌ Error: {str(e)[:50]}", show_alert=True)
        return False
```

**Key Design Decision:** Uses `cb.edit_message_text()` instead of `cb.message.edit_text()` to support inline messages where `cb.message` can be None.

#### safe_evaldoc_delete()
**Purpose:** Safely delete messages with None check

```python
async def safe_evaldoc_delete(cb: CallbackQuery):
    try:
        if cb.message:  # Check existence before delete
            await cb.message.delete()
        return True
    except Exception as e:
        Altruix.log(f"[evaldoc] Error deleting message: {e}", level=40)
        return False
```

### 3. Callback Handler

```python
@Altruix.bot.on_callback_query(filters.regex(r"^evaldoc_"))
@iuser_check  # Security protection
@log_errors
async def evaldoc_callback_handler(c: Client, q: CallbackQuery):
    data = q.data
    
    # Handle close button
    if data == "evaldoc_close":
        success = await safe_evaldoc_delete(q)
        if success:
            await safe_evaldoc_answer(q, "Menu closed.", show_alert=False)
        return
    
    # Handle noop (disabled buttons)
    if data == "evaldoc_noop":
        await safe_evaldoc_answer(q, "⚠️ Already at boundary", show_alert=False)
        return
    
    # Handle page navigation
    if data.startswith("evaldoc_page_"):
        try:
            page_num = int(data.split("_")[-1])
        except ValueError:
            await safe_evaldoc_answer(q, "❌ Invalid page", show_alert=True)
            return
        
        # Validate page number
        if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
            await safe_evaldoc_answer(q, f"❌ Page must be 1-{len(EVAL_DOC_PAGES)}", show_alert=True)
            return
        
        # Get page content and keyboard
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = get_evaldoc_keyboard(page_num)
        
        # Update message
        success = await safe_evaldoc_edit(q, page_content, reply_markup=keyboard)
        if success:
            await safe_evaldoc_answer(q, f"📄 Page {page_num}/{len(EVAL_DOC_PAGES)}", show_alert=False)
```

**Error Handling:**
- Invalid page number: Show alert
- Out of range: Show alert with valid range
- Edit failure: Log error + show alert
- Expired callback: Silently ignore

### 4. Inline Handler

```python
@Altruix.bot.on_inline_query(filters.regex(r"^evaldoc(?:_page_)?(\d+)?"))
@iuser_check  # Security protection
@log_errors
async def evaldoc_inline_handler(client: Client, query: InlineQuery):
    # Extract page number from query
    match = query.matches[0]
    page_str = match.group(1)
    page_num = int(page_str) if page_str else 1
    
    # Validate page number
    if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
        page_num = 1
    
    # Get page content and keyboard
    page_content = EVAL_DOC_PAGES[page_num - 1]
    keyboard = get_evaldoc_keyboard(page_num)
    
    await query.answer(
        results=[
            InlineQueryResultArticle(
                title=f"📚 Eval & Reval Guide - Page {page_num}/15",
                description=f"Comprehensive documentation for eval/reval usage",
                input_message_content=InputTextMessageContent(
                    page_content,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                ),
                reply_markup=keyboard
            )
        ],
        cache_time=0
    )
```

**Inline Query Patterns:**
- `evaldoc` → Page 1
- `evaldoc_page_5` → Page 5
- `evaldoc 3` → Page 3 (if supported by regex)

### 5. Command Handler

```python
@Altruix.register_on_cmd(
    ["evaldoc", "evalhelp", "evalguide"],
    cmd_help={...}
)
@log_errors
async def eval_documentation_handler_inline(c: Client, m: Message):
    # Parse page number from user input
    page_input = m.user_input.strip() if m.user_input else "1"
    page_num = int(page_input)
    
    # Validate page number
    if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
        return await m.reply_msg("❌ Invalid page number")
    
    # Get bot assistant
    bot = Altruix.bot_manager.get_bot(user_id) or Altruix.bot
    bot_username = Altruix.bot_manager.get_bot_username(user_id)
    
    # Try inline mode first (works in ANY chat)
    if bot_username:
        try:
            results = await c.get_inline_bot_results(bot_username, f"evaldoc_page_{page_num}")
            if results.results:
                sent = await c.send_inline_bot_result(
                    m.chat.id,
                    results.query_id,
                    results.results[0].id
                )
                if sent:
                    await m.delete_if_self()
                    return
        except Exception as e:
            Altruix.log(f"[evaldoc] Inline mode failed: {e}, falling back", level=30)
    
    # Fallback to direct bot message
    page_content = EVAL_DOC_PAGES[page_num - 1]
    keyboard = get_evaldoc_keyboard(page_num)
    await bot.send_message(m.chat.id, page_content, reply_markup=keyboard)
    await m.delete_if_self()
```

**Fallback Strategy:**
1. Try inline mode (works everywhere)
2. Fallback to direct bot message (only if bot in chat)
3. Final fallback: Edit original message

## Security Design

### Authorization Flow
```
User clicks button
    ↓
@iuser_check decorator
    ↓
Check if user is owner/sudo
    ├─ YES → Execute handler
    └─ NO → Show custom alert + log activity
```

### Protected Operations
- All callback button clicks
- All inline query requests
- Page navigation
- Close button

### Security Features
- Session ID authorization for inline queries
- Activity logging (configurable)
- Custom alert messages for unauthorized users
- No data leakage to unauthorized users

## Error Handling Strategy

### Callback Errors
```
Error Type                  → Handling Strategy
─────────────────────────────────────────────────
NoneType (cb.message)      → Use cb.edit_message_text()
Expired callback           → Silently ignore in answer()
Invalid page number        → Show alert with valid range
Network error              → Log + show user alert
Message already deleted    → Check existence before delete
```

### Inline Query Errors
```
Error Type                  → Handling Strategy
─────────────────────────────────────────────────
Invalid page number        → Default to page 1
Bot not found              → Fallback to direct message
Network error              → Log error + retry
```

## Performance Considerations

### Optimization Strategies
1. **Keyboard Caching:** Keyboards generated on-demand (lightweight)
2. **Page Content:** Static list (no database queries)
3. **Inline Query:** Cache time = 0 (always fresh)
4. **Callback Response:** Immediate (no async operations)

### Resource Usage
- Memory: ~50KB for EVAL_DOC_PAGES
- CPU: Minimal (simple string operations)
- Network: 1 API call per interaction

## Testing Strategy

### Unit Tests
- Keyboard generation for all 15 pages
- Boundary conditions (page 1, page 15)
- Invalid page numbers
- Emoji integrity

### Integration Tests
- Callback handler with all button types
- Inline handler with various queries
- Security decorator functionality
- Error handling scenarios

### Manual Tests
- All 7 button types on all 15 pages
- Inline mode in different chat types
- Security protection verification
- Emoji rendering on different devices

## Deployment Considerations

### Prerequisites
- Pyrogram library installed
- Bot token configured
- Inline mode enabled for bot
- iuser_check decorator available

### Configuration
- No additional configuration needed
- Uses existing Altruix.bot
- Uses existing bot_manager

### Monitoring
- Log all errors at level 40 (ERROR)
- Log inline mode fallbacks at level 30 (WARNING)
- Log successful operations at level 20 (INFO)

## Future Enhancements

### Potential Improvements
1. Search functionality within documentation
2. Bookmarking favorite pages
3. Multi-language support
4. Custom themes
5. Export to PDF
6. Code snippet execution from docs

### Scalability
- Current design supports up to 100 pages
- Keyboard generation scales linearly
- No database dependencies
- Stateless design (easy to scale)

## References

### Design Patterns Used
- **Safe Wrapper Pattern:** Helper functions for error handling
- **Fallback Pattern:** Inline → Direct → Edit
- **Decorator Pattern:** @iuser_check for security
- **Strategy Pattern:** Different handlers for different modes

### Inspiration
- xauto_pro_gcast.py: Safe callback handling pattern
- xmention_logger_user.py: Inline mode implementation
- Telegram Bot API: Inline query best practices
