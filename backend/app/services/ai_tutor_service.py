from collections.abc import AsyncGenerator
import json
import logging
from uuid import UUID

from arq.connections import ArqRedis
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.unit_of_work import IUnitOfWork
from app.models.chat import CEFRLevel, ChatMessage, MessageRole
from app.schemas.chat import AIStreamChunk

settings = get_settings()
logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None)


class AITutorService:
    def __init__(self, uow: IUnitOfWork, redis: ArqRedis) -> None:
        self.uow = uow
        self.redis = redis

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generates 1536-dim embedding vector using text-embedding-3-small."""
        response = await client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    def _build_system_prompt(
        self,
        target_language: str,
        cefr_level: CEFRLevel | str,
        vocab_hints: list[str],
    ) -> str:
        """Constructs level-calibrated language tutor directives with dynamic vocab injections."""
        level_str = cefr_level.value if isinstance(cefr_level, CEFRLevel) else str(cefr_level)

        level_guides = {
            "A1": "Use simple present tense, common foundational words, short sentences. Limit vocabulary strictly.",
            "A2": "Use basic past/future tenses, routine compound sentences. Keep idioms to a minimum.",
            "B1": "Converse naturally on common topics. Introduce moderate colloquialisms and subordinate clauses.",
            "B2": "Use detailed descriptions, abstract ideas, and varied register.",
            "C1": "Speak fluently with nuanced stylistic variations, complex idioms, and native pacing.",
            "C2": "Employ full native range, subtleties, and cultural idioms.",
        }

        guide = level_guides.get(level_str, level_guides["A1"])
        prompt = (
            f"You are a friendly, encouraging {target_language} language tutor.\n"
            f"Target student proficiency level: {level_str}. Guideline: {guide}\n"
            f"Always reply predominantly in {target_language}.\n"
        )

        if vocab_hints:
            prompt += f"Try to incorporate or contextualize these review terms if natural: {', '.join(vocab_hints)}.\n"

        return prompt

    async def _analyze_message(
        self,
        message: ChatMessage,
        user_input: str,
        target_language: str,
        cefr_level: CEFRLevel,
        user_id: UUID,
    ) -> AsyncGenerator[str, None]:
        prompt = (
            f"You are an encouraging {target_language} language tutor for a learner at {cefr_level.value}.\n"
            f"Analyze this learner message: {json.dumps(user_input, ensure_ascii=False)}\n"
            "Return a JSON object with a corrections array. Each correction must contain "
            "original, replacement, and a concise explanation. Return an empty corrections array "
            "when the message is correct. Also include used_vocabulary as an array of vocabulary "
            "items the learner used. Also return vocabulary_hints as an array of two or three "
            f"useful {target_language} words or short phrases related to the learner's message. "
            "Return target-language terms only, without translations.\n"
            'Schema: {"corrections":[{"original":"...","replacement":"...","explanation":"..."}],'
            '"used_vocabulary":["..."],"vocabulary_hints":["..."]}'
        )

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            analysis = json.loads(response.choices[0].message.content or "{}")
            if not isinstance(analysis, dict) or not isinstance(analysis.get("corrections"), list):
                raise ValueError("Grammar analysis response has an invalid shape.")

            message.audio_metadata = {
                **(message.audio_metadata or {}),
                "grammar_analysis": analysis,
            }
            await self.uow.commit()

            used_vocabulary = analysis.get("used_vocabulary", [])
            if isinstance(used_vocabulary, list):
                words = [word.strip() for word in used_vocabulary if isinstance(word, str) and word.strip()]
                if words:
                    quality = analysis.get("fluency_score_0_to_5", 3)
                    if type(quality) is not int or not 0 <= quality <= 5:
                        quality = 3
                    try:
                        await self.redis.enqueue_job(
                            "update_srs_reviews",
                            user_id=str(user_id),
                            words=words,
                            quality=quality,
                        )
                    except Exception:
                        logger.exception("Failed to queue vocabulary review updates for user %s", user_id)

            vocabulary_hints = analysis.get("vocabulary_hints", [])
            if isinstance(vocabulary_hints, list):
                for word in vocabulary_hints:
                    if isinstance(word, str) and word.strip():
                        yield self._sse_chunk(
                            "vocab_hint",
                            word.strip(),
                            {"word": word.strip()},
                        )

            for correction in analysis["corrections"]:
                if not isinstance(correction, dict):
                    continue
                original = correction.get("original")
                replacement = correction.get("replacement")
                explanation = correction.get("explanation")
                if not all(isinstance(value, str) for value in (original, replacement, explanation)):
                    continue
                yield self._sse_chunk(
                    "grammar_correction",
                    f"{original} → {replacement}: {explanation}",
                    {"original": original, "replacement": replacement, "explanation": explanation},
                )
        except Exception:
            logger.exception("Failed grammar analysis for message %s", message.id)
            yield self._sse_chunk(
                "error",
                "Grammar feedback is temporarily unavailable for this message.",
            )

    @staticmethod
    def _sse_chunk(event: str, delta: str = "", metadata: dict | None = None) -> str:
        payload = AIStreamChunk(event=event, delta=delta, metadata=metadata).model_dump_json()
        return f"data: {payload}\n\n"

    async def stream_chat_turn(
        self,
        session_id: UUID,
        user_id: UUID,
        user_message_content: str,
    ) -> AsyncGenerator[str, None]:
        """
        1. Appends user message.
        2. Retrieves session, conversation history, and matching vocabulary vectors.
        3. Streams the LLM tokens as SSE chunks.
        4. Writes assistant message to DB on completion.
        5. Analyzes the learner message and queues spaced-repetition updates.
        """
        # 1. Store user message in DB
        user_msg = await self.uow.chat.append_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=user_message_content,
        )
        await self.uow.commit()

        # 2. Fetch recent conversation context (latest 10 messages)
        session, history = await self.uow.chat.get_session_with_history(
            session_id=session_id,
            user_id=user_id,
            message_limit=10,
        )
        if not session:
            yield f"data: {AIStreamChunk(event='done', delta='Session not found').model_dump_json()}\n\n"
            return

        # 3. Semantic RAG: Vector search vocabulary items relevant to user's input
        input_vector = await self._generate_embedding(user_message_content)
        similar_vocab = await self.uow.vocabulary.search_similar_vocabulary(
            user_id=user_id,
            target_language=session.target_language,
            embedding=input_vector,
            limit=4,
            max_distance=0.40,
        )
        vocab_words = [vocab.word for vocab, _ in similar_vocab]
        for word in vocab_words:
            yield self._sse_chunk("vocab_hint", word, {"word": word})

        # 4. Construct message payload
        system_instruction = self._build_system_prompt(
            target_language=session.target_language,
            cefr_level=session.current_cefr_level,
            vocab_hints=vocab_words,
        )

        messages = [{"role": "system", "content": system_instruction}]
        for msg in history:
            role_val = msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role)
            messages.append({"role": role_val.lower(), "content": msg.content})

        # 5. Execute streaming completion
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            temperature=0.7,
        )

        full_assistant_response: list[str] = []

        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_assistant_response.append(delta)
                sse_payload = AIStreamChunk(event="token", delta=delta).model_dump_json()
                yield f"data: {sse_payload}\n\n"

        assistant_content = "".join(full_assistant_response)

        # 6. Save assistant turn in DB within current UoW transaction
        await self.uow.chat.append_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
        )
        await self.uow.commit()

        async for analysis_chunk in self._analyze_message(
            message=user_msg,
            user_input=user_message_content,
            target_language=session.target_language,
            cefr_level=session.current_cefr_level,
            user_id=user_id,
        ):
            yield analysis_chunk

        yield self._sse_chunk("done")