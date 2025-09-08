# evaluation/hardmath.py
import json
import os
import asyncio
import re
from typing import Dict, Any, List
from core.meta_agent import MetaAgent


class HardMathRunner:
    """
    运行 HARDMath 评估的工具，包含进化和测试两个阶段。
    """

    def __init__(self, meta_agent: MetaAgent, config: Dict[str, Any]):
        """初始化 HardMath 运行器"""
        self.config = config
        self.meta_agent = meta_agent
        self.train_dataset_path = os.path.join("data", "hardmath", "HARDMath_train.json")
        self.test_dataset_path = os.path.join("data", "hardmath", "HARDMath_test.json")

    def _extract_final_answer(self, text: str) -> str:
        """从文本中提取最终答案，优先匹配 \\boxed{...}"""
        # 优先寻找 \boxed{...} 格式的答案
        boxed_match = re.search(r"\\boxed{(.+?)}", text, re.DOTALL)
        if boxed_match:
            return boxed_match.group(1).strip()

        # 其次寻找 #### <答案> 格式
        match = re.search(r"####\s*(.+)$", text)
        if match:
            return match.group(1).strip()

        # 如果都没有，返回空字符串
        return ""

    def _load_problems(self, file_path: str, num_problems: int = None) -> List[Dict[str, Any]]:
        """从 JSON 文件加载 HARDMath 问题"""
        if not os.path.exists(file_path):
            print(f"错误: 数据集文件未找到于 {file_path}")
            return []

        with open(file_path, "r", encoding='utf-8') as f:
            data = json.load(f)

        # 将字典转换为列表
        problems = [value for key, value in data.items()]

        if num_problems is not None:
            return problems[:num_problems]
        return problems

    async def run_evolution_phase(self, num_problems: int = 10):
        """
        运行进化阶段。
        使用训练数据集来运行 MetaAgent，并允许其进行自我进化。
        """
        print("\n--- [HardMath] Starting Evolution Phase ---")
        train_problems = self._load_problems(self.train_dataset_path, num_problems)
        if not train_problems:
            return

        for i, problem in enumerate(train_problems):
            print(f"Evolving on problem {i + 1}/{len(train_problems)}...")

            # 在进化阶段，allow_evolution 设置为 True
            await self._evaluate_problem(problem, allow_evolution=True)

        print("--- [HardMath] Evolution Phase Completed ---\n")

    async def run_testing_phase(self, num_problems: int = None) -> Dict[str, Any]:
        """
        运行测试阶段。
        使用测试数据集来评估进化后的 MetaAgent 的性能。
        """
        print("--- [HardMath] Starting Testing Phase ---")
        test_problems = self._load_problems(self.test_dataset_path, num_problems)
        if not test_problems:
            return {}

        results = []
        for i, problem in enumerate(test_problems):
            print(f"Testing on problem {i + 1}/{len(test_problems)}: {problem['question'][:50]}...")

            # 在测试阶段，allow_evolution 设置为 False
            result = await self._evaluate_problem(problem, allow_evolution=False)
            results.append(result)

            passed_str = "PASS" if result["passed"] else "FAIL"
            print(f"  Result: {passed_str}")
            print(f"    Generated: {result['generated_answer'][:80]}...")
            print(f"    Correct:   {result['correct_answer'][:80]}...")

        stats = self._compute_statistics(results)
        print("--- [HardMath] Testing Phase Completed ---\n")

        return {
            "results": results,
            "accuracy": stats["accuracy"],
            "total_problems": len(test_problems),
            "passed_problems": stats["passed_count"]
        }

    async def _evaluate_problem(self, problem: Dict[str, Any], allow_evolution: bool) -> Dict[str, Any]:
        """评估单个问题"""
        task = f"Please solve the following advanced math problem from the HARDMath dataset. Provide a detailed, step-by-step reasoning and enclose your final answer in \\boxed{{...}}.\n\nQuestion: {problem['question']}"

        result_obj = await self.meta_agent.handle_task(task, allow_evolution=allow_evolution)
        generated_text = result_obj.get("output", "") # MODIFIED HERE

        generated_answer = self._extract_final_answer(generated_text)
        correct_answer = problem.get('answer_val', '')

        # 简单的字符串匹配来判断正确性
        passed = generated_answer == correct_answer

        return {
            "question": problem['question'],
            "generated_solution": generated_text,
            "generated_answer": generated_answer,
            "correct_answer": correct_answer,
            "passed": passed
        }

    def _compute_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评估统计信息"""
        passed_count = sum(1 for result in results if result["passed"])
        total_count = len(results)
        return {
            "passed_count": passed_count,
            "accuracy": passed_count / total_count if total_count > 0 else 0
        }
