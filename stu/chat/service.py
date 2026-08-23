"""Chat service: orchestrates memory context, LLM gateway, and history."""

from __future__ import annotations

from loguru import logger

from ..config import AppConfig
from ..models import ChatMessage, ChatRequest, ChatResponse, ChatRole
from ..memory.service import MemoryService
from ..llm.gateway import LLMGateway


class ChatService:
    def __init__(
        self,
        config: AppConfig,
        memory_service: MemoryService,
        llm_gateway: LLMGateway,
    ):
        self.config = config
        self.memory_service = memory_service
        self.llm_gateway = llm_gateway
        self._histories: dict[str, list[ChatMessage]] = {}

    def get_history(self, project_id: str) -> list[ChatMessage]:
        return list(self._histories.get(project_id, []))

    async def send_message(self, project_id: str, req: ChatRequest) -> ChatResponse:
        if project_id not in self._histories:
            self._histories[project_id] = []

        history = self._histories[project_id]

        user_msg = ChatMessage(role=ChatRole.USER, content=req.message)
        history.append(user_msg)
        self._trim_history(history)

        messages = self._build_messages(project_id, history)

        try:
            response_text = await self.llm_gateway.generate(messages)
        except Exception as e:
            logger.error(f"LLM call failed for project {project_id}: {e}")
            response_text = f"I encountered an error while generating a response: {e}"

        assistant_msg = ChatMessage(role=ChatRole.ASSISTANT, content=response_text)
        history.append(assistant_msg)
        self._trim_history(history)

        logger.info(f"Chat response generated for project {project_id}")
        return ChatResponse(message=assistant_msg, project_id=project_id)

    def _trim_history(self, history: list[ChatMessage]) -> None:
        limit = self.config.chat.history_limit
        if len(history) > limit:
            history[:] = history[-limit:]

    def _build_messages(
        self, project_id: str, history: list[ChatMessage]
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        messages.append({
            "role": "system",
            "content": self.config.chat.system_prompt,
        })

        try:
            memories = self.memory_service.list_memories(project_id, query=None)
            if memories:
                context_parts = []
                for mem in memories[:5]:
                    snippet = mem.content[:200].replace("\n", " ")
                    context_parts.append(f"- {mem.title}: {snippet}")
                context = "\n".join(context_parts)
                messages.append({
                    "role": "system",
                    "content": f"Relevant project memory:\n{context}",
                })
        except Exception as e:
            logger.warning(f"Failed to retrieve memory context: {e}")

        for msg in history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        return messages
