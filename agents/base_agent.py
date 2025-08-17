# agents/base_agent.py
import asyncio
from utils.api_utils import ApiManager
from typing import Optional
import httpx


class Agent:
    """基础Agent类，所有Agent的基类"""

    def __init__(self, name: str, system_prompt: str, config: Optional[dict] = None):
        """
        初始化Agent

        Args:
            name: Agent名称
            system_prompt: 系统提示
            config: 配置字典
        """
        self.name = name
        self.system_prompt = system_prompt
        self.config = config or {}
        # print(self.config)
        self.api_manager = ApiManager(self.config)
        self.role = None  # 新增，允许后续赋值
        self.type = None  # 新增，允许后续赋值

    async def generate(self, prompt: str) -> str:
        """
        生成文本响应

        Args:
            prompt: 输入提示

        Returns:
            生成的文本响应
        """
        # 组合系统提示和用户提示
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        # return await self.api_manager.generate_chat_completion(messages)
        try:
            return await self.api_manager.generate_chat_completion(messages)
        except httpx.TimeoutException as e:
            error_message = f"Error: Request timed out. The API call took too long to respond. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message
        except httpx.HTTPStatusError as e:
            error_message = f"Error: API connection error. Received status code {e.response.status_code}. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message
        except RuntimeError as e:
            # This catches errors from api_utils when parsing the response
            error_message = f"Error: A runtime error occurred while generating chat completion. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message
        except Exception as e:
            error_message = f"Error: An unexpected error occurred in agent generation. Details: {type(e).__name__} - {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            return error_message

