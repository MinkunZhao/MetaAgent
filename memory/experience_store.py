# memory/experience_store.py
import os
import json
from typing import Dict, Any, List

class ExperienceStore:
    def __init__(self, path: str = "results/experience.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump([], f)

    async def store_experience(self, experience: Dict[str, Any]) -> None:
        """将经验追加存储到本地JSON文件"""
        data = await self.load_all_experiences()
        data.append(experience)
        try:
            with open(self.path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error storing experience: {e}")

    async def load_all_experiences(self) -> List[Dict[str, Any]]:
        """加载所有存储的经验"""
        try:
            with open(self.path, "r", encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return []