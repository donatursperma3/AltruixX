import html
import sys
import io

# Fix Windows encoding for emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mocking the constants/structs for the demo
processed_chats = 5
total_chats = 10
total_deleted = 145
is_final = False

log_entries = [
    "✅ (<code>-100123456789</code>) : <a href='https://t.me/c/123456789/1'>Public Group A</a> | <code>45</code> msgs",
    "✅ (<code>-100987654321</code>) : <a href='https://t.me/c/987654321/1'>Testing Channel</a> | <code>100</code> msgs",
    "⏭ (<code>-100555444333</code>) : <a href='https://t.me/c/555444333/1'>Old Chat</a> | <code>0</code> msgs",
    "✅ (<code>-100111222333</code>) : <a href='https://t.me/c/111222333/1'>Project Chat</a> | <code>12</code> msgs",
    "🔄 (<code>-100444555666</code>) : <a href='https://t.me/c/444555666/1'>Current Chat</a> | <i>Processing...</i>",
]

def build_demo_log(processed, total, deleted, entries, final=False):
    header = (
        f"📋 <b>Batch Log — Auto Global Purgeme</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{processed}</b>/{total} │ ✅ <b>{deleted}</b> msgs\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    
    body = ""
    for entry in entries:
        body += f"{entry}\n"
    
    status_line = "🏁 <b>Completed</b>" if final else "🔄 <i>Processing...</i>"
    footer = f"━━━━━━━━━━━━━━━━━━\n{status_line}"
    
    return f"<blockquote expandable>{header}{body}{footer}</blockquote>"

print("\n--- [EXAMPLE LOG OUTPUT: BATCH LOG] ---")
print(build_demo_log(processed_chats, total_chats, total_deleted, log_entries))
print("---------------------------------------\n")

print("--- [EXAMPLE LOG OUTPUT: FINAL STATE] ---")
print(build_demo_log(total_chats, total_chats, total_deleted + 50, log_entries + ["✅ (<code>-100444555666</code>) : <a href='https://t.me/c/444555666/1'>Current Chat</a> | <code>50</code> msgs"], final=True))
print("-----------------------------------------\n")
