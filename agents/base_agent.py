# agents/base_agent.py
import asyncio
from utils.api_utils import ApiManager
from typing import Optional, Dict, Any
import httpx

class Agent:
    """基础Agent类，所有Agent的基类"""

    def __init__(self, name: str, system_prompt: str, config: Optional[dict] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.config = config or {}
        self.api_manager = ApiManager(self.config)
        self.role = None
        self.type = None

    async def generate(self, prompt: str) -> str:
        """
        生成纯文本响应。所有自我评估逻辑已被移除。
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = await self.api_manager.generate_chat_completion(messages)
            return raw_response.strip()

        except httpx.TimeoutException as e:
            error_message = f"Error: Request timed out. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message
        except httpx.HTTPStatusError as e:
            error_message = f"Error: API connection error. Status code {e.response.status_code}. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message
        except Exception as e:
            error_message = f"Error: An unexpected error occurred. Details: {type(e).__name__} - {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message