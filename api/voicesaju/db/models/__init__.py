"""ORM model exports.

Importing this package registers every model on `Base.metadata`, so it is
safe (and required) to import here in `alembic/env.py` for autogenerate
and at startup before any session is opened.
"""

from __future__ import annotations

from voicesaju.db.models.character_voices import CharacterVoice
from voicesaju.db.models.devices import Device
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.intro_audio_clips import IntroAudioClip
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.profiles import Profile
from voicesaju.db.models.quote_cards import QuoteCard
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.db.models.reading_followups import ReadingFollowup
from voicesaju.db.models.reading_transcripts import ReadingTranscript
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.refunds import Refund
from voicesaju.db.models.saju_charts import SajuChart
from voicesaju.db.models.subscriptions import Subscription
from voicesaju.db.models.tarot_cards import TarotCard
from voicesaju.db.models.tarot_draws import TarotDraw
from voicesaju.db.models.tone_eval_cases import ToneEvalCase
from voicesaju.db.models.tone_prompt_versions import TonePromptVersion
from voicesaju.db.models.tone_violation_events import ToneViolationEvent
from voicesaju.db.models.users import User

__all__ = [
    "CharacterVoice",
    "Device",
    "FreeToken",
    "IntroAudioClip",
    "Payment",
    "Profile",
    "QuoteCard",
    "Reading",
    "ReadingAudio",
    "ReadingFollowup",
    "ReadingTranscript",
    "Refund",
    "SajuChart",
    "Subscription",
    "TarotCard",
    "TarotDraw",
    "ToneEvalCase",
    "TonePromptVersion",
    "ToneViolationEvent",
    "User",
]
