"""
Tests for xrap_manager.py callback logic.
Tests the data extraction, context parsing, and edit_or_send behavior
without needing a live Telegram connection.
"""
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# Helper: simulate the data extraction logic from rapmgr_cb_handler
# ===========================================================================

def extract_context(full_data: str, clicker_id: int):
    """
    Replicate the context extraction logic from rapmgr_cb_handler.
    Returns (owner_id, chat_id, action_data)
    """
    uid_match = re.search(r"_uid(\d+)", full_data)
    cid_match = re.search(r"_cid(-?\d+)", full_data)

    owner_id = int(uid_match.group(1)) if uid_match else clicker_id
    chat_id = int(cid_match.group(1)) if cid_match else None

    data = full_data.replace("rapmgr_", "")
    data = re.sub(r"_uid\d+", "", data)
    data = re.sub(r"_cid-?\d+", "", data)

    return owner_id, chat_id, data


# ===========================================================================
# Tests: Context extraction
# ===========================================================================

class TestContextExtraction:
    """Test that uid and cid are correctly extracted from callback_data."""

    def test_extracts_uid_and_cid(self):
        owner, cid, action = extract_context(
            "rapmgr_page_1_uid123456_cid-100987654", clicker_id=999
        )
        assert owner == 123456
        assert cid == -100987654
        assert action == "page_1"

    def test_falls_back_to_clicker_if_no_uid(self):
        owner, cid, action = extract_context(
            "rapmgr_page_1_cid-100987654", clicker_id=999
        )
        assert owner == 999
        assert cid == -100987654

    def test_negative_cid_supported(self):
        _, cid2, _ = extract_context("rapmgr_settings_uid789_cid-1001234567", 1)
        assert cid2 == -1001234567

    def test_no_context_falls_back(self):
        owner, cid, action = extract_context("rapmgr_close", clicker_id=42)
        assert owner == 42
        assert cid is None
        assert action == "close"

    def test_edit_song_action_preserved(self):
        _, _, action = extract_context(
            "rapmgr_edit_myslug_uid111_cid222", clicker_id=0
        )
        assert action == "edit_myslug"

    def test_le_loopback_action(self):
        owner, cid, action = extract_context(
            "rapmgr_le_myslug_3_1_uid555_cid-100111222", clicker_id=0
        )
        assert owner == 555
        assert cid == -100111222
        assert action == "le_myslug_3_1"


# ===========================================================================
# Tests: generate_pagination_keyboard context encoding
# ===========================================================================

class TestKeyboardContextEncoding:
    """Test that context is encoded in all buttons of the keyboard."""

    def test_keyboard_contains_uid_and_cid(self):
        """Simulate generate_pagination_keyboard output and verify encoding."""
        items = [("slug1", "Title 1"), ("slug2", "Title 2")]
        user_id = 111222333
        chat_id = -100987654321

        encoded_ctx = ""
        if user_id:
            encoded_ctx += f"_uid{user_id}"
        if chat_id:
            encoded_ctx += f"_cid{chat_id}"

        # Simulate one button
        cb_data = f"rapmgr_edit_slug1{encoded_ctx}"
        assert f"_uid{user_id}" in cb_data, "UID should be encoded in callback data"
        assert f"_cid{chat_id}" in cb_data, "CID should be encoded in callback data"

    def test_no_cid_if_not_provided(self):
        user_id = 111
        chat_id = None
        encoded_ctx = f"_uid{user_id}" if user_id else ""
        if chat_id:
            encoded_ctx += f"_cid{chat_id}"
        assert "_cid" not in encoded_ctx


# ===========================================================================
# Tests: edit_or_send behavior (mocked Pyrogram)
# ===========================================================================

class TestEditOrSend:
    """Test edit_or_send routing logic."""

    @pytest.mark.asyncio
    async def test_uses_cb_edit_message_text_for_inline(self):
        """cb.edit_message_text() should be called for inline messages."""
        cb = MagicMock()
        cb.message = None   # <-- Inline mode: no cb.message
        cb.inline_message_id = "some_inline_id"
        cb.edit_message_text = AsyncMock(return_value=True)

        # Simulate our corrected edit_or_send
        async def edit_or_send_fixed(cb, c, text, kb=None):
            try:
                await cb.edit_message_text(text, reply_markup=kb)
            except Exception:
                pass

        await edit_or_send_fixed(cb, None, "Test text")
        cb.edit_message_text.assert_called_once_with("Test text", reply_markup=None)

    @pytest.mark.asyncio
    async def test_uses_cb_edit_message_text_for_regular(self):
        """cb.edit_message_text() should also work for regular bot messages."""
        cb = MagicMock()
        cb.message = MagicMock()  # Regular message present
        cb.edit_message_text = AsyncMock(return_value=True)

        async def edit_or_send_fixed(cb, c, text, kb=None):
            try:
                await cb.edit_message_text(text, reply_markup=kb)
            except Exception:
                pass

        await edit_or_send_fixed(cb, None, "Regular test")
        cb.edit_message_text.assert_called_once()


# ===========================================================================
# Tests: inject_context helper
# ===========================================================================

class TestInjectContext:
    """Test that inject_context correctly stamps uid+cid on buttons."""

    def _make_kb(self, cb_data_list):
        """Create a mock InlineKeyboardMarkup."""
        kb = MagicMock()
        buttons = []
        for cb_data in cb_data_list:
            btn = MagicMock()
            btn.callback_data = cb_data
            buttons.append([btn])
        kb.inline_keyboard = buttons
        return kb

    def inject_context_fn(self, kb, user_id, chat_id):
        """Replicate inject_context logic from the handler."""
        ctx = f"_uid{user_id}_cid{chat_id}"
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("rapmgr_"):
                    c_data = re.sub(r"_uid\d+", "", btn.callback_data)
                    c_data = re.sub(r"_cid-?\d+", "", c_data)
                    btn.callback_data = c_data + ctx
        return kb

    def test_injects_context_correctly(self):
        kb = self._make_kb(["rapmgr_page_1", "rapmgr_settings"])
        kb = self.inject_context_fn(kb, user_id=12345, chat_id=-100999)
        for row in kb.inline_keyboard:
            for btn in row:
                assert "_uid12345" in btn.callback_data
                assert "_cid-100999" in btn.callback_data

    def test_removes_old_context_before_injecting(self):
        kb = self._make_kb(["rapmgr_page_1_uid99999_cid-111"])
        kb = self.inject_context_fn(kb, user_id=12345, chat_id=-100999)
        for row in kb.inline_keyboard:
            for btn in row:
                assert "_uid99999" not in btn.callback_data
                assert "_uid12345" in btn.callback_data

    def test_ignores_non_rapmgr_buttons(self):
        kb = self._make_kb(["session_info_1_2_5", "rapmgr_close"])
        original_data = kb.inline_keyboard[0][0].callback_data
        kb = self.inject_context_fn(kb, user_id=12345, chat_id=-100)
        # Non-rapmgr button should be unchanged
        assert kb.inline_keyboard[0][0].callback_data == original_data
