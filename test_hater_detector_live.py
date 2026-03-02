"""
Live test script untuk hater detector
Jalankan script ini untuk test apakah handler terpicu
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_hater_detector():
    """Test hater detector functionality."""
    print("=" * 60)
    print("HATER DETECTOR LIVE TEST")
    print("=" * 60)
    print()
    
    print("📋 CHECKLIST:")
    print()
    
    # 1. Check if feature enabled
    print("1. Cek status feature:")
    print("   Jalankan: .haterstatus")
    print("   Expected: Status: 🟢 ENABLED")
    print()
    
    # 2. Check responses
    print("2. Cek responses:")
    print("   Jalankan: .haterresponses")
    print("   Expected: Total: 1 atau lebih")
    print()
    
    # 3. Check if user blocked
    print("3. Verify user blocked userbot:")
    print("   Jalankan: .send <hater_user_id> test")
    print("   Expected: Error UserIsBlocked atau PeerIdInvalid")
    print()
    
    # 4. Test mention
    print("4. Test mention di group:")
    print("   Minta user hater untuk mention userbot: @userbotname test")
    print("   Expected log:")
    print("   [Hater Detector] 🔔 hater_detector triggered for message <id>")
    print("   [Hater Detector] Processing message from <user_id>")
    print("   [Hater Detector] User <user_id> blocked status: True")
    print("   [Hater Detector] ✅ Response sent successfully!")
    print()
    
    # 5. Test reply
    print("5. Test reply di group:")
    print("   Minta user hater untuk reply message userbot")
    print("   Expected log:")
    print("   [Hater Detector] 🔔 hater_reply_detector triggered for message <id>")
    print("   [Hater Detector] Message is reply to us from <user_id>")
    print("   [Hater Detector] Processing message from <user_id>")
    print("   [Hater Detector] User <user_id> blocked status: True")
    print("   [Hater Detector] ✅ Response sent successfully!")
    print()
    
    print("=" * 60)
    print("DEBUGGING TIPS:")
    print("=" * 60)
    print()
    
    print("Jika handler TIDAK terpicu (tidak ada log 🔔):")
    print("  - Pastikan message dari user biasa (bukan bot)")
    print("  - Pastikan bukan service message (join/leave)")
    print("  - Pastikan di group biasa (bukan log chat)")
    print("  - Cek apakah ada plugin lain yang block handler")
    print()
    
    print("Jika handler terpicu tapi tidak ada response:")
    print("  - Cek log: 'Feature disabled for user' → jalankan .hateron")
    print("  - Cek log: 'No responses configured' → jalankan .hateraddresponse")
    print("  - Cek log: 'blocked status: False' → user belum block userbot")
    print()
    
    print("Jika response gagal dikirim:")
    print("  - Cek log untuk error message")
    print("  - Cek permission userbot di group")
    print("  - Cek apakah group restrict userbot")
    print()

if __name__ == "__main__":
    asyncio.run(test_hater_detector())
