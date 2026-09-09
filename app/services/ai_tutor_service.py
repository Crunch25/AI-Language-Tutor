from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import json
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.unit_of_work import IUnitOfWork
from app.models.chat import CEFRLevel, MessageRole
from app.schemas.chat import AIStreamChunk

settings = get_settings()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None)


class AITutorService:
    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

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
        5. Enqueues background grammar analysis to Redis.
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

        # 7. Notify client stream is complete
        yield f"data: {AIStreamChunk(event='done', delta='').model_dump_json()}\n\n"

        # 8. Dispatch async background tasks to Redis via ARQ
        redis = await create_pool(RedisSettings.from_dsn(str(settings.REDIS_URL)))
        await redis.enqueue_job(
            "analyze_grammar_and_syntax",
            message_id=str(user_msg.id),
            user_id = str(user_id),
            user_input=user_message_content,
            target_language=session.target_language,
            cefr_level=session.current_cefr_level.value,
        )
        await redis.close()