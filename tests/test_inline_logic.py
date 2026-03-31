import re
import base64
import unittest

class TestInlineLogic(unittest.TestCase):
    def test_settings_regex(self):
        pattern = re.compile(r"^settings(?:\s|$)")
        
        # Test original query format (no metadata)
        self.assertTrue(bool(pattern.match("settings")))
        
        # Test new query format with metadata
        self.assertTrue(bool(pattern.match("settings cid=-100123 ctit=dGVzdA==")))
        
        # Test false positives
        self.assertFalse(bool(pattern.match("settings_menu")))
        self.assertFalse(bool(pattern.match("settings_close")))
        
    def test_session_info_regex(self):
        pattern = re.compile(r"^session_(\d+)(?:_(\d+))?")
        
        # Test original query format (index only)
        m1 = pattern.match("session_0")
        self.assertTrue(bool(m1))
        self.assertEqual(m1.group(1), "0")
        
        # Test original query format (index and page)
        m2 = pattern.match("session_1_2")
        self.assertTrue(bool(m2))
        self.assertEqual(m2.group(1), "1")
        self.assertEqual(m2.group(2), "2")
        
        # Test new query format with metadata
        m3 = pattern.match("session_0 cid=-123 ctit=QWJj")
        self.assertTrue(bool(m3))
        self.assertEqual(m3.group(1), "0")
        
    def test_base64_logic(self):
        # 1. Encoding (simulate xsettings_user.py)
        chat_titles = ["Group Test", "Group Test 🚀", "My Super Group - 123", "   "]
        
        for title in chat_titles:
            encoded_title = base64.b64encode(title.encode('utf-8')).decode('utf-8')
            query = f"settings cid=-100 ctit={encoded_title}"
            
            # 2. Decoding (simulate settings.py / session_info.py)
            extracted_title = "N/A"
            if m := re.search(r"ctit=([^&\s]+)", query):
                try:
                    extracted_title = base64.b64decode(m.group(1)).decode('utf-8')
                except Exception as e:
                    self.fail(f"Decoding failed for title '{title}': {e}")
                
            self.assertEqual(title, extracted_title, f"Mismatch for title: {title}")

if __name__ == '__main__':
    unittest.main()
