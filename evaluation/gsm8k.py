# evaluation/gsm8k.py
import json
import os
import asyncio
import re
from typing import Dict, Any, List
import urllib.request
from core.meta_agent import MetaAgent


class Gsm8kRunner:
    """
    运行GSM8K评估的工具
    """

    def __init__(self, meta_agent: MetaAgent, config: Dict[str, Any]):
        """初始化GSM8K运行器"""
        self.config = config
        self.meta_agent = meta_agent
        self.dataset_path = os.path.join("data", "gsm", "gsm.jsonl")

    def _extract_final_answer(self, text: str) -> str:
        """从文本中提取最终答案"""
        # 寻找 "#### <数字>" 格式的答案
        match = re.search(r"####\s*([0-9,.]+)$", text)
        if match:
            answer = match.group(1).replace(",", "")
            # 处理可能尾随的句点
            if answer.endswith('.'):
                answer = answer[:-1]
            return answer

        # 如果没有找到标准格式，回退到寻找文本中最后一个数字
        matches = re.findall(r'[\d\.]+', text)
        if matches:
            return matches[-1]

        return ""

    async def run_evaluation(self, num_problems: int = None) -> Dict[str, Any]:
        """
        运行GSM8K评估

        Args:
            num_problems: 要评估的问题数量，None表示全部

        Returns:
            包含评估结果的字典
        """
        await self._ensure_dataset()
        problems = self._load_problems(num_problems)
        results = []

        for i, problem in enumerate(problems):
            print(f"Evaluating problem {i + 1}/{len(problems)}: {problem['question'][:50]}...")
            result = await self._evaluate_problem(problem)
            results.append(result)
            passed = "PASS" if result["passed"] else "FAIL"
            print(f"  Result: {passed} (Agent: {result['generated_answer']}, Correct: {result['correct_answer']})")

        stats = self._compute_statistics(results)
        return {
            "results": results,
            "accuracy": stats["accuracy"],
            "total_problems": len(problems),
            "passed_problems": stats["passed_count"]
        }

    async def _evaluate_problem(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个问题"""
        task = f"Please solve the following math word problem. Show your reasoning step-by-step and provide the final answer at the end in the format #### <answer>.\n\nQuestion: {problem['question']}"

        result = await self.meta_agent.handle_task(task)
        generated_text = result["output"]

        generated_answer = self._extract_final_answer(generated_text)
        correct_answer = self._extract_final_answer(problem['answer'])

        passed = generated_answer == correct_answer

        return {
            "question": problem['question'],
            "generated_solution": generated_text,
            "generated_answer": generated_answer,
            "correct_answer": correct_answer,
            "passed": passed
        }

    async def _ensure_dataset(self) -> None:
        """确保GSM8K数据集存在"""
        os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)

        if not os.path.exists(self.dataset_path):
            print("Downloading GSM8K dataset...")
            url = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"
            try:
                urllib.request.urlretrieve(url, self.dataset_path)
                print("Download complete.")
            except Exception as e:
                print(f"Failed to download dataset: {e}")
                raise

    def _load_problems(self, num_problems: int = None) -> List[Dict[str, Any]]:
        """加载GSM8K问题"""
        problems = []
        with open(self.dataset_path, "r", encoding='utf-8') as f:
            for line in f:
                problems.append(json.loads(line))

        if num_problems is not None:
            problems = problems[:num_problems]
        return problems

    def _compute_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评估统计信息"""
        passed_count = sum(1 for result in results if result["passed"])
        total_count = len(results)
        return {
            "passed_count": passed_count,
            "accuracy": passed_count / total_count if total_count > 0 else 0
        }
