import os
from typing import Tuple
import logging
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

class LLMIntentClassifier:
    def __init__(self):
        self.use_mock = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
        self.llm = None
        self.chain = None
        if not self.use_mock:
            try:
                self.llm = ChatOllama(
                    model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                    temperature=0,
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                )
                self.chain = self._create_chain()
                logger.info("LLM classifier initialised")
            except Exception as e:
                logger.warning(f"LLM init failed: {e}. Using mock.")
                self.use_mock = True

    def _create_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an HR intent classifier. Respond ONLY with one word: scheduling, leave, compliance, or clarification.
Examples:
- 'book meeting' -> scheduling
- 'vacation days' -> leave
- 'policy' -> compliance
- 'hello' -> clarification"""),
            ("user", "{input}")
        ])
        return prompt | self.llm | StrOutputParser()

    async def classify(self, message: str) -> Tuple[str, float]:
        if not self.use_mock and self.chain:
            try:
                intent = await self.chain.ainvoke({"input": message})
                intent = intent.strip().lower()
                if intent in ["scheduling", "leave", "compliance", "clarification"]:
                    return intent, 0.92
                else:
                    return self._mock_classify(message)
            except Exception as e:
                logger.error(f"LLM error: {e}. Falling back.")
                return self._mock_classify(message)
        else:
            return self._mock_classify(message)

    def _mock_classify(self, message: str) -> Tuple[str, float]:
        msg_lower = message.lower()
        keywords = {
            "scheduling": ["schedule", "meeting", "interview"],
            "leave": ["leave", "vacation", "pto", "time off"],
            "compliance": ["compliance", "policy", "legal"],
        }
        for intent, kw_list in keywords.items():
            if any(kw in msg_lower for kw in kw_list):
                return intent, 0.8
        return "clarification", 0.45