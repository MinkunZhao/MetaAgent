# evaluation/aime.py
import json
import os
import re
from typing import Dict, Any, List
from core.meta_agent import MetaAgent


class AimeRunner:
    """
    运行 AIME 2025 评估的工具。
    """

    def __init__(self, meta_agent: MetaAgent, config: Dict[str, Any]):
        """初始化 Aime 运行器"""
        self.config = config
        self.meta_agent = meta_agent
        self.dataset_path = os.path.join("data", "aime", "aime2025.jsonl")

    def _extract_final_answer(self, text: str) -> str:
        """从文本中提取最终答案，优先匹配 \\boxed{...}"""
        boxed_match = re.search(r"\\boxed{(.+?)}", text, re.DOTALL)
        if boxed_match:
            return boxed_match.group(1).strip()
        match = re.search(r"####\s*(.+)$", text)
        if match:
            return match.group(1).strip()
        return ""

    def _load_problems(self, num_problems: int = None) -> List[Dict[str, Any]]:
        """从 JSON Lines (.jsonl) 文件加载 AIME 问题"""
        if not os.path.exists(self.dataset_path):
            print(f"错误: 数据集文件未找到于 {self.dataset_path}")
            print(f"正在尝试创建示例数据集于 {self.dataset_path}...")
            os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)
            example_data = [
                {"question": "Find the sum of all integer bases $b>9$ for which $17_{b}$ is a divisor of $97_{b}$.",
                 "answer": "70",
                "solution": "We are tasked with finding the number of integer bases $b>9$ such that $\\cfrac{9b+7}{b+7}\\in\\textbf{Z}$..."},
                {
                "question": "On $\\triangle ABC$ points $A,D,E$, and $B$ lie that order on side $\\overline{AB}$ with $AD=4, DE=16$, and $EB=8$. Points $A,F,G$, and $C$ lie in that order on side $\\overline{AC}$ with $AF=13, FG=52$, and $GC=26$. Let $M$ be the reflection of $D$ through $F$, and let $N$ be the reflection of $G$ through $E$. Quadrilateral $DEGF$ has area 288. Find the area of heptagon $AFNBCEM$.",
                    "answer": "588",
                    "solution": "Note that the triangles outside $\\triangle ABC$ have the same height..."}
                ]
            # 以 .jsonl 格式写入示例文件
            with open(self.dataset_path, "w", encoding='utf-8') as f:
                for entry in example_data:
                    f.write(json.dumps(entry) + "\n")
            print("示例数据集创建成功。")

        problems = []
        # 按行读取和解析 .jsonl 文件
        with open(self.dataset_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():  # 确保不是空行
                    problems.append(json.loads(line))

        if num_problems is not None:
            return problems[:num_problems]
        return problems

    async def run_evaluation(self, num_problems: int = None, allow_evolution: bool = False) -> Dict[str, Any]:
        """
        运行评估阶段。
        如果 allow_evolution 为 True，则在处理每个问题后都会触发潜在的自我进化。
        如果为 False，则仅进行测试而不进化智能体。
        """
        phase_name = "Evolutionary Evaluation" if allow_evolution else "Testing"
        print(f"--- [AIME 2025] Starting {phase_name} Phase ---")

        problems = self._load_problems(num_problems)
        if not problems:
            return {}

        results = []
        for i, problem in enumerate(problems):
            print(f"Processing problem {i + 1}/{len(problems)}: {problem['question'][:50]}...")
            result = await self._evaluate_problem(problem, allow_evolution=allow_evolution)
            results.append(result)

            passed_str = "PASS" if result["passed"] else "FAIL"
            print(f"  Result: {passed_str} in {result['attempts']} attempt(s).")
            print(f"    Generated: {result['generated_answer'][:80]}...")
            print(f"    Correct:   {result['correct_answer'][:80]}...")

        stats = self._compute_statistics(results)
        print(f"--- [AIME 2025] {phase_name} Phase Completed ---\n")

        return {
            "results": results,
            "accuracy": stats["accuracy"],
            "total_problems": len(problems),
            "passed_problems": stats["passed_count"]
        }

    async def _evaluate_problem(self, problem: Dict[str, Any], allow_evolution: bool) -> Dict[str, Any]:
        """评估单个问题，并在失败时触发学习循环。"""
        initial_task = f"Please solve the following advanced math problem from the AIME 2025 dataset. Provide a detailed, step-by-step reasoning and enclose your final answer in \\boxed{{...}}.\n\nQuestion: {problem['question']}"
        correct_answer = problem.get('answer', '')
        max_attempts = 2  # 首次尝试 + 1次学习后尝试
        current_attempt = 0
        passed = False
        generated_text = ""
        generated_answer = ""
        task = initial_task

        while not passed and current_attempt < max_attempts:
            current_attempt += 1
            print(f"    Attempt {current_attempt}/{max_attempts}...")

            # 只有在学习后才触发进化
            should_evolve_this_turn = allow_evolution and (current_attempt > 1)
            result_obj = await self.meta_agent.handle_task(task, allow_evolution=should_evolve_this_turn)
            generated_text = result_obj.get("output", "")

            # 如果是学习任务的输出，我们需要分离出答案和学习内容
            if "### Corrected Solution Implementation" in generated_text:
                solution_part = generated_text.split("### Corrected Solution Implementation")[1]
                generated_answer = self._extract_final_answer(solution_part)
            else:
                generated_answer = self._extract_final_answer(generated_text)

            passed = str(generated_answer) == str(correct_answer)

            if not passed and current_attempt < max_attempts:
                print("    Attempt failed. Triggering learning from solution...")
                # 构建学习任务
                task = self._create_learning_task(problem, generated_text)

        return {
            "question": problem['question'],
            "generated_solution": generated_text,
            "generated_answer": generated_answer,
            "correct_answer": correct_answer,
            "passed": passed,
            "attempts": current_attempt
        }

    def _create_learning_task(self, problem: Dict[str, Any], incorrect_solution: str) -> str:
            """创建一个特殊的任务，要求MetaAgent从错误中学习。"""
            return f"""You are in a self-correction and learning loop. You previously failed to solve a math problem. Your new task is to deeply analyze your mistake by comparing it to the correct solution, extract abstract lessons, and then provide a corrected solution.

    **Problem Context:**
    - **Original Problem:** {problem['question']}
    - **Your Incorrect Solution:** 
    ---
    {incorrect_solution}
    ---
    - **The Correct Step-by-Step Solution is:**
    ---
    {problem.get('solution', 'No detailed solution provided.')}
    ---

    **Your New Task:**
    You MUST provide your response in the following structured format, using the exact headings provided.

    ### Root Cause Analysis of the Error
    In this section, precisely explain WHY the previous solution was incorrect. Pinpoint the specific logical flaw, miscalculation, or misunderstanding by comparing your work to the correct solution.

    ### Abstract Takeaways and Lessons Learned
    This is the most critical part. Based on your analysis, formulate general, reusable principles or heuristics. Do not just restate the error. Instead, abstract the lesson. For example, instead of "I forgot to check b > 9", a good takeaway would be "For base-N problems, always explicitly list and verify all constraints on the base (e.g., N > largest digit) at the beginning of the solution."

    ### Corrected Solution Implementation
    Execute a new, correct solution from scratch, applying the lessons you just learned. Provide the full, detailed, step-by-step mathematical reasoning. Show all your work clearly.
    Finally, ensure your implementation concludes with the final answer enclosed in `\\boxed{{...}}`.
    """

    def _compute_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评估统计信息"""
        passed_count = sum(1 for result in results if result["passed"])
        total_count = len(results)
        return {
            "passed_count": passed_count,
            "accuracy": passed_count / total_count if total_count > 0 else 0
        }