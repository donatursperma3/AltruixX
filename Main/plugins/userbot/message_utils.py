# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import os
from Main import Altruix
from gtts import gTTS, lang
from ...utils.file_helpers import run_in_exc
from deep_translator import GoogleTranslator

# Compatibility layer for googletrans LANGUAGES
try:
    _langs = GoogleTranslator().get_supported_languages(as_dict=True)
    LANGUAGES = {v: k for k, v in _langs.items()}
except Exception:
    LANGUAGES = {"en": "english", "id": "indonesian", "auto": "automatic"}


class MockTranslation:
    def __init__(self, text, src, dest):
        self.text = text
        self.src = src
        self.dest = dest


def translate_wrapper(text, src, dest):
    try:
        translator = GoogleTranslator(source=src, target=dest)
        translation_text = translator.translate(text)
        return MockTranslation(translation_text, src, dest)
    except Exception as e:
        return MockTranslation(str(e), src, dest)


translate_now = run_in_exc(translate_wrapper)


@run_in_exc
def tts_(to_tts, lang):
    file_name = f"tts_{to_tts[:5]}.mp3" if len(to_tts) > 5 else f"tts_{to_tts}.mp3"
    tts = gTTS(to_tts, lang=lang)
    tts.save(file_name)
    return file_name

@Altruix.register_on_cmd(
    "tts",
    cmd_help={
        "help": "Convert text to speech",
        "example": "tts en",
    },
    requires_reply=True,
)
async def tts_now(c, m):
    msg_ = await m.handle_message("PROCESSING")
    if not m.reply_to_message.text:
        return await msg_.edit_msg("INVALID_REPLY")
    input_ = m.user_input
    langs_ = lang.tts_langs()
    lang_ = "en"
    if input_ and langs_.get(input_.lower()):
        lang_ = input_.lower()
    elif not langs_.get(lang_):
        await msg_.edit("INVALID_LANG")
        lang_ = "en"
    file_ = await tts_(m.reply_to_message.text, lang_)
    await m.reply_voice(
        file_,
        caption="<b>TTS </b> \n<b>Converted and processed by Altruix</b>",
        quote=True,
    )
    await msg_.delete_if_self()
    if os.path.exists(file_):
        os.remove(file_)


@Altruix.register_on_cmd(
    "tr",
    cmd_help={"help": "Translate text to your desired language", "example": "tr en"},
    requires_reply=True,
)
async def translate_(c, m):
    _m_ = await m.handle_message("PROCESSING")
    to_tr = m.reply_to_message.text or m.reply_to_message.caption
    if not to_tr:
        return await _m_.edit_msg("REPLY_TO_MESSAGE")
    to_tr = m.reply_to_message.text or m.reply_to_message.caption
    from_lang = "auto"
    lang_to = "en"
    if m.user_input:
        input_ = m.user_input.strip().split(" ", 1)
        lang_to = input_[0]
        from_lang = input_[1] if len(input_) != 1 else "auto"
    
    # Check language validity
    if not LANGUAGES.get(lang_to.lower()):
        return await _m_.edit_msg("LANGUAGE_NOT_SUPPORTED", string_args=(lang_to))
    if from_lang != "auto" and not LANGUAGES.get(from_lang.lower()):
        return await _m_.edit_msg("LANGUAGE_NOT_SUPPORTED", string_args=(from_lang))
        
    translation = await translate_now(
        to_tr, src=from_lang.lower(), dest=lang_to.lower()
    )
    
    await _m_.edit_msg(
        "TRANSLATED",
        string_args=(
            LANGUAGES.get(translation.src) or translation.src,
            LANGUAGES.get(translation.dest) or translation.dest,
            translation.text,
        ),
    )
