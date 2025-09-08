# agents/base_agent.py
import asyncio
from utils.api_utils import ApiManager
from typing import Optional, Dict, Any
import httpx
from utils.json_utils import extract_and_parse_json


class Agent:
    """基础Agent类，所有Agent的基类"""

    def __init__(self, name: str, system_prompt: str, config: Optional[dict] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.config = config or {}
        self.api_manager = ApiManager(self.config)
        self.role = None
        self.type = None

    async def generate(self, prompt: str) -> Dict[str, Any]:
        """
        生成文本响应，并包含自我评估的置信度。
        """
        # MODIFIED: Define the separator for more robust splitting
        separator = "--- SELF-EVALUATION ---"
        confidence_prompt = (
            f"{prompt}\n\n"
            f"{separator}\n"
            "After providing your primary response, you MUST output a single valid JSON object on a new line. "
            "This JSON object should represent your self-evaluation of the response you just generated. "
            "The JSON object must contain two keys:\n"
            "1. 'confidence': A float from 0.0 (not confident) to 1.0 (very confident) assessing the quality and correctness of your response.\n"
            "2. 'reasoning': A brief string explaining your confidence score, noting any assumptions or potential weaknesses."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": confidence_prompt}
        ]

        default_error_response = {
            "response": "An error occurred during generation.",
            "confidence": 0.0,
            "reasoning": "System-level error."
        }

        try:
            raw_response = await self.api_manager.generate_chat_completion(messages)

            response_part = raw_response
            evaluation_json = None

            # MODIFIED: Robust splitting based on the separator
            if separator in raw_response:
                parts = raw_response.split(separator)
                response_part = parts[0].strip()
                # The JSON part is in the second half
                evaluation_json = extract_and_parse_json(parts[1])
            else:
                # Fallback if separator is missing, try to find JSON anyway
                evaluation_json = extract_and_parse_json(raw_response)

            confidence = 0.5  # Default confidence
            reasoning = "Could not parse self-evaluation."

            if isinstance(evaluation_json, dict) and 'confidence' in evaluation_json and 'reasoning' in evaluation_json:
                confidence = float(evaluation_json.get('confidence', 0.5))
                reasoning = evaluation_json.get('reasoning', "Parsed, but keys missing.")

            return {
                "response": response_part,
                "confidence": confidence,
                "reasoning": reasoning
            }

        except httpx.TimeoutException as e:
            error_message = f"Error: Request timed out. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            default_error_response["response"] = error_message
            return default_error_response
        except httpx.HTTPStatusError as e:
            error_message = f"Error: API connection error. Status code {e.response.status_code}. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            default_error_response["response"] = error_message
            return default_error_response
        except RuntimeError as e:
            error_message = f"Error: Runtime error during generation. Details: {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            default_error_response["response"] = error_message
            return default_error_response
        except Exception as e:
            error_message = f"Error: An unexpected error occurred. Details: {type(e).__name__} - {e}"
            print(f"AGENT ERROR ({self.name}): {error_message}")
            default_error_response["response"] = error_message
            return default_error_response
