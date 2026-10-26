import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings
from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.chat import ChatMessage, VocabularyMemory

settings = get_settings()
logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None)


def calculate_sm2(
    quality: int,
    repetition_count: int,
    ease_factor: float,
    interval_days: int,
) -> tuple[int, float, int]:
    """
    Computes SuperMemo-2 (SM-2) spaced repetition parameters.
    
    Quality Score: 0 to 5.
    Returns: (new_repetitions, new_ease_factor, new_interval_days)
    """
    if quality < 3:
        # Reset streak on failure
        return 0, max(1.3, ease_factor - 0.2), 1

    # Update ease factor based on performance
    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(1.3, round(new_ef, 4))

    # Calculate interval schedule
    if repetition_count == 0:
        new_interval = 1
    elif repetition_count == 1:
        new_interval = 6
    else:
        new_interval = int(round(interval_days * new_ef))

    return repetition_count + 1, new_ef, new_interval


async def analyze_grammar_and_syntax(
    ctx: dict[str, Any],
    message_id: str,
    user_id: str,
    user_input: str,
    target_language: str,
    cefr_level: str,
) -> None:
    """Evaluates message syntax, persists corrections to metadata, and updates vocabulary usage."""
    prompt = (
        f"You are an analytical {target_language} grammar examiner for level {cefr_level}.\n"
        f"Analyze this student text: '{user_input}'.\n"
        "Return a pure JSON object without markdown fences with schema:\n"
        "{\n"
        '  "is_correct": boolean,\n'
        '  "corrections": [{"original": string, "replacement": string, "explanation": string}],\n'
        '  "used_vocabulary": [string],\n'
        '  "fluency_score_0_to_5": integer\n'
        "}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")

        # Save analysis to database
        async with async_session_factory() as session:
            stmt = select(ChatMessage).where(ChatMessage.id == UUID(message_id))
            result = await session.execute(stmt)
            msg = result.scalar_one_or_none()

            if msg:
                msg.audio_metadata = {
                    **(msg.audio_metadata or {}),
                    "grammar_analysis": data,
                }
                await session.commit()

        # If any target vocabulary was identified in the turn, trigger SM-2 update
        if data.get("used_vocabulary"):
            await ctx["redis"].enqueue_job(
                "update_srs_reviews",
                user_id = user_id,
                words=data["used_vocabulary"],
                quality=data.get("fluency_score_0_to_5", 3),
            )

    except Exception:
        logger.exception("Failed grammar analysis for message %s", message_id)


async def update_srs_reviews(ctx: dict[str, Any], user_id: str, words: list[str], quality: int) -> None:
    """Updates SRS interval for successfully recalled vocabulary items."""
    target_user_uuid = UUID(user_id)

    async with async_session_factory() as session:
        for word in words:
            stmt = select(VocabularyMemory).where(
                VocabularyMemory.user_id == target_user_uuid,
                VocabularyMemory.word.ilike(word.strip())
            )
            result = await session.execute(stmt)
            vocab = result.scalar_one_or_none()

            if vocab:
                reps, ef, interval = calculate_sm2(
                    quality=quality,
                    repetition_count=vocab.repetition_count,
                    ease_factor=vocab.ease_factor,
                    interval_days=vocab.interval_days,
                )
                vocab.repetition_count = reps
                vocab.ease_factor = ef
                vocab.interval_days = interval
                vocab.next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)

        await session.commit()


class WorkerSettings:
    functions = [analyze_grammar_and_syntax, update_srs_reviews]
    redis_settings = RedisSettings.from_dsn(str(settings.REDIS_URL))