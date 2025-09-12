# utils/api_utils.py
'''import os
import json
import asyncio
from typing import Dict, Any, List, Optional
import openai
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

# 定义一个重试装饰器，专门用于处理临时的API错误
# 这会使得函数在遇到指定的openai错误时自动重试
# 等待策略是指数退避，最短1秒，最长60秒，总共尝试6次
retry_on_api_error = retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError))
)


class ApiManager:
    """
    管理与API的交互
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化API管理器"""
        self.config = config
        self.api_key = os.environ.get("OPENAI_API_KEY", config.get("openai_api_key", ""))
        self.default_model = config.get("default_model", "")

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable or add it to the config.")

        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    @retry_on_api_error
    async def generate_completion(self,
                                  prompt: str,
                                  model: Optional[str] = None,
                                  temperature: float = 0.7,
                                  ) -> str:
        """生成文本完成"""
        model = model or self.default_model

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            # 处理非瞬时性的API错误（例如，无效请求）
            print(f"A non-retriable API error occurred: {e}")
            return f"Error generating completion: {str(e)}"
        except Exception as e:
            # 处理其他未知错误
            print(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred while generating completion: {str(e)}"

    @retry_on_api_error
    async def generate_chat_completion(self,
                                       messages: List[Dict[str, str]],
                                       model: Optional[str] = None,
                                       temperature: float = 1,
                                       ) -> str:
        """生成聊天完成"""
        model = model or self.default_model

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            # 处理非瞬时性的API错误
            print(f"A non-retriable API error occurred: {e}")
            return f"Error generating chat completion: {str(e)}"
        except Exception as e:
            # 处理其他未知错误
            print(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred while generating chat completion: {str(e)}"

    async def batch_generate(self,
                             prompts: List[str],
                             model: Optional[str] = None,
                             temperature: float = 1,
                             ) -> List[str]:
        """
        批量生成完成
        注意：asyncio.gather会并发执行任务。如果请求量非常大，
        可能会瞬间达到速率限制。可以考虑使用信号量（Semaphore）来控制并发数。
        """
        # 使用Semaphore来限制同时进行的API调用数量，防止速率超限
        # 例如，我们限制最多同时有10个并发请求
        sem = asyncio.Semaphore(10)

        async def controlled_generation(prompt: str) -> str:
            async with sem:
                # 在进入信号量控制的区域后，可以稍微等待一下，进一步平滑请求
                await asyncio.sleep(0.5)
                return await self.generate_completion(prompt, model, temperature)

        tasks = [
            controlled_generation(prompt)
            for prompt in prompts
        ]

        # gather会等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理可能在gather中捕获的异常
        final_results = []
        for res in results:
            if isinstance(res, Exception):
                print(f"A task in batch failed after all retries: {res}")
                final_results.append(f"Error: {str(res)}")
            else:
                final_results.append(res)

        return final_results'''



'''import os
from typing import Dict, Any, List, Optional

import httpx
import asyncio


class ApiManager:
    """
    管理与依步 yibuapi.com LLM 接口的异步交互
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化 API 管理器"""
        # 1. API Key：优先从环境变量 YIBU_API_KEY 获取，再回退到 config
        self.api_key = config.get("yibu_api_key")
        if not self.api_key:
            raise ValueError(
                "API key 未提供，请在 config 中配置 yibu_api_key。"
            )

        # 2. Base URL 和默认参数
        # 官网示例中 base_url 是 https://yibuapi.com
        # 真正的请求端点需要在此基础上拼接，例如 /v1/chat/completions
        self.base_url = config.get("yibu_base_url")
        self.default_model = config.get("default_model")
        self.timeout = config.get("timeout")
        self.default_max_tokens = config.get("max_tokens")
        self.default_temperature = config.get("temperature")
        # print(self.base_url)
        # print(self.default_model)
        # print(self.timeout)
        # print(self.default_max_tokens)
        # print(self.default_temperature)

        # 3. 创建一个全局的 AsyncClient，可复用连接池
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _call_yibu(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """内部：发起异步 HTTP POST 请求到 yibu 接口"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 修正请求的 URL，需要指向具体的 chat/completions 端点
        endpoint_url = f"{self.base_url}/v1/chat/completions"

        response = await self._client.post(endpoint_url, json=payload, headers=headers)

        # 抛出 HTTP 错误状态码 (e.g., 4xx, 5xx)
        response.raise_for_status()
        return response.json()

    async def generate_completion(
            self,
            prompt: str,
            system_prompt: str = "You are a helpful assistant.",
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> str:
        """
        异步生成单轮文本完成 (为了简化，底层调用 chat completion)
        """
        # 使用 chat completion 的格式来构建 messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # 直接复用 generate_chat_completion 方法
        return await self.generate_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def generate_chat_completion(
            self,
            messages: List[Dict[str, str]],
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> str:
        """
        异步生成多轮聊天完成
        """
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # 根据需要可以添加 stream: False 等其他参数
        }

        data = await self._call_yibu(payload)

        # 依步 API 的返回格式与 OpenAI 兼容，因此解析方式是正确的
        try:
            # 检查返回的数据结构是否包含预期的键
            if "choices" in data and data["choices"]:
                message = data["choices"][0].get("message")
                if message and "content" in message:
                    return message["content"]
            raise RuntimeError(f"响应格式不符合预期: {data!r}")
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"解析响应时出错，响应数据: {data!r}")

    async def batch_generate(self, prompts: List[str], model=None, temperature=None, max_tokens=None) -> List[str]:
        """
        使用 asyncio.gather 并行处理批量生成请求，效率更高
        """
        tasks = [
            self.generate_completion(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            for prompt in prompts
        ]

        # gather 会并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理可能出现的异常
        return [str(res) if not isinstance(res, Exception) else f"[Error: {res}]" for res in results]

    async def close(self):
        """关闭 AsyncClient 连接池"""
        await self._client.aclose()'''



import os
from typing import Dict, Any, List, Optional

import httpx
import asyncio


class ApiManager:
    """
    管理与云雾 yunwu.ai LLM 接口的异步交互
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化 API 管理器"""
        # 1. API Key：优先从环境变量 YUNWU_API_KEY 获取，再回退到 config
        self.api_key = os.environ.get("YUNWU_API_KEY") or config.get("yunwu_api_key", "")
        if not self.api_key:
            raise ValueError(
                "API key 未提供，请在 config 中配置 yunwu_api_key 或设置 YUNWU_API_KEY 环境变量。"
            )

        # 2. Base URL 和默认参数
        # yunwu.ai 的 base_url 是 https://yunwu.ai
        # 真正的请求端点需要在此基础上拼接，例如 /v1/chat/completions
        self.base_url = config.get("yunwu_base_url", "https://yunwu.ai")
        self.default_model = config.get("default_model")
        self.timeout = config.get("timeout", 30)  # 增加一个默认超时时间
        self.default_max_tokens = config.get("max_tokens")
        self.default_temperature = config.get("temperature")

        # 3. 创建一个全局的 AsyncClient，可复用连接池
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _call_yunwu(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """内部：发起异步 HTTP POST 请求到 yunwu.ai 接口"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 修正请求的 URL，需要指向具体的 chat/completions 端点
        endpoint_url = f"{self.base_url}/v1/chat/completions"

        response = await self._client.post(endpoint_url, json=payload, headers=headers)

        # 抛出 HTTP 错误状态码 (e.g., 4xx, 5xx)
        response.raise_for_status()
        return response.json()

    async def generate_completion(
            self,
            prompt: str,
            system_prompt: str = "You are a helpful assistant.",
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> str:
        """
        异步生成单轮文本完成 (为了简化，底层调用 chat completion)
        """
        # 使用 chat completion 的格式来构建 messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # 直接复用 generate_chat_completion 方法
        return await self.generate_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def generate_chat_completion(
            self,
            messages: List[Dict[str, str]],
            model: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> str:
        """
        异步生成多轮聊天完成
        """
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        # 仅在 max_tokens 有效时才添加到 payload 中
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        data = await self._call_yunwu(payload)

        # yunwu.ai API 的返回格式与 OpenAI 兼容
        try:
            # 检查返回的数据结构是否包含预期的键
            if "choices" in data and data["choices"]:
                message = data["choices"][0].get("message")
                if message and "content" in message:
                    return message["content"]
            raise RuntimeError(f"响应格式不符合预期: {data!r}")
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"解析响应时出错，响应数据: {data!r}")

    async def batch_generate(self, prompts: List[str], model=None, temperature=None, max_tokens=None) -> List[str]:
        """
        使用 asyncio.gather 并行处理批量生成请求，效率更高
        """
        tasks = [
            self.generate_completion(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            for prompt in prompts
        ]

        # gather 会并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理可能出现的异常
        return [str(res) if not isinstance(res, Exception) else f"[Error: {res}]" for res in results]

    async def close(self):
        """关闭 AsyncClient 连接池"""
        await self._client.aclose()
