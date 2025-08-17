import os
import json
from typing import Dict, Any

class KnowledgeBase:
    def __init__(self, path: str = "results/knowledge.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump([], f)

    async def add_knowledge(self, task_type: str, knowledge: Dict[str, Any]) -> None:
        """将知识追加存储到本地JSON文件"""
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except Exception:
            data = []
        data.append({"task_type": task_type, "knowledge": knowledge})
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)


