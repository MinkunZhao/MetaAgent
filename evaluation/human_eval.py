# evaluation/human_eval.py
import json
import os
import asyncio
from operator import index
from typing import Dict, Any, List
import tempfile
import subprocess
import importlib.util
import urllib.request

from core.meta_agent import MetaAgent
from utils.evaluation import CodeEvaluator


class HumanEvalRunner:
    """
    运行HumanEval评估的工具
    """

    def __init__(self, meta_agent: MetaAgent, config: Dict[str, Any]):
        """初始化HumanEval运行器"""
        self.config = config
        self.meta_agent = meta_agent
        self.evaluator = CodeEvaluator()
        self.dataset_path = os.path.join("data", "human_eval", "human-eval-v2-20210705.jsonl")

    async def run_evaluation(self, num_problems: int = None) -> Dict[str, Any]:
        """
        运行HumanEval评估

        Args:
            num_problems: 要评估的问题数量，None表示全部

        Returns:
            包含评估结果的字典
        """
        # 确保数据集存在
        # await self._ensure_dataset()

        # 加载问题
        problems = self._load_problems(num_problems)

        # 运行评估
        results = []
        for i, problem in enumerate(problems):
            print(f"Evaluating problem {i + 1}/{len(problems)}: {problem['task_id']}")

            result = await self._evaluate_problem(problem)
            results.append(result)

            # 输出进度
            passed = "PASS" if result["passed"] else "FAIL"
            print(f"  Result: {passed}")

        # 计算统计信息
        stats = self._compute_statistics(results)

        # 组合结果
        return {
            "results": results,
            "pass@1": stats["pass@1"],
            "total_problems": len(problems),
            "passed_problems": stats["passed_count"]
        }

    async def _evaluate_problem(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个问题"""
        # 构建任务描述
        task = f"""
Please write a Python function that satisfies the following requirements:

Return ONLY the function implementation without explanation!

Function Name: {problem['entry_point']}

Problem Description:
{problem['prompt']}

Your function should match this signature exactly: {problem['entry_point']}{self._format_signature(problem['entry_point'], problem['prompt'])}

You should return the answer in the following format:

Return ONLY the function implementation without explanation!

[code start]

……

[code end]

"""

        # 使用Meta Agent生成代码
        result = await self.meta_agent.handle_task(task)
        generated_code = result["output"]
        # print(generated_code)
        # print("\n------------------------------------------------\n")
        # print(problem["entry_point"])

        # 提取函数代码
        function_code = self._extract_function(generated_code, problem["entry_point"])
        # print("\n------------------------------------------------\n")
        # print(function_code)

        # 评估代码
        if problem["prompt"][:4] == "from" or problem["prompt"][:6] == "import":
            ind = problem["prompt"].find("\n\n\n")
            # print("\n------------------------------------------------\n")
            # print(problem["prompt"][:ind])
            # print("\n------------------------------------------------\n")
            test_results = await self._test_against_canonical(
                problem["prompt"][:ind] + "\n\n" + function_code,
                problem["entry_point"],
                problem["test"]
            )
        else:
            test_results = await self._test_against_canonical(
                function_code,
                problem["entry_point"],
                problem["test"]
            )

        return {
            "task_id": problem["task_id"],
            "generated_code": function_code,
            "passed": test_results["passed"],
            "test_results": test_results
        }

    async def _test_against_canonical(self,
                                      function_code: str,
                                      entry_point: str,
                                      test_code: str) -> Dict[str, Any]:
        """
        测试生成的代码是否通过规范测试
        """
        # 创建一个临时文件来测试代码
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            # 将生成的函数与测试代码组合
            f.write(f"{function_code}\n\n{test_code}\n\n")
            # 添加运行测试的代码
            f.write(f"""
if __name__ == "__main__":
    try:
        check({entry_point})
        print("PASS")
    except Exception as e:
        print(f"FAIL: {{str(e)}}")
""")
            temp_path = f.name

        # 运行测试
        try:
            process = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True
            )

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()

            passed = "PASS" in stdout and "FAIL" not in stdout

            return {
                "passed": passed,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": process.returncode
            }
        except Exception as e:
            return {
                "passed": False,
                "error": str(e)
            }
        finally:
            # 删除临时文件
            os.unlink(temp_path)

    def _extract_function(self, code: str, function_name: str) -> str:
        """从生成的代码中提取函数"""
        # 尝试找到函数定义
        lines = code.split("\n")
        function_start = -1

        for i, line in enumerate(lines):
            l = line.lstrip()
            if l.startswith(f"def {function_name}"):
            # if line.find(f"def {function_name}"):
                function_start = i
                break

        if function_start == -1:
            # 没有找到函数，返回整个代码
            return code

        # 找到函数的结束
        function_end = len(lines)
        indent = None

        for i in range(function_start + 1, len(lines)):
            if lines[i].strip() == "":
                continue

            current_indent = len(lines[i]) - len(lines[i].lstrip())

            if indent is None:
                indent = current_indent
            elif current_indent <= 0 or (indent > 0 and current_indent < indent):
                function_end = i
                break
        # print(function_start)
        # print(function_end)

        # 提取函数代码
        leading_spaces = len(lines[function_start]) - len(lines[function_start].lstrip())
        if leading_spaces != 0:
            for i in range(function_start, function_end):
                lines[i] = lines[i][leading_spaces:]
        function_code = "\n".join(lines[function_start:function_end])

        return function_code

    async def _ensure_dataset(self) -> None:
        """确保HumanEval数据集存在"""
        os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)

        if not os.path.exists(self.dataset_path):
            print("Downloading HumanEval dataset...")
            url = "https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl"

            try:
                urllib.request.urlretrieve(url, self.dataset_path)
                print("Download complete.")
            except Exception as e:
                print(f"Failed to download dataset: {e}")
                raise

    def _load_problems(self, num_problems: int = None) -> List[Dict[str, Any]]:
        """加载HumanEval问题"""
        problems = []

        with open(self.dataset_path, "r") as f:
            for line in f:
                problems.append(json.loads(line))

        if num_problems is not None:
            problems = problems[:num_problems]

        return problems

    def _compute_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评估统计信息"""
        passed_count = sum(1 for result in results if result["passed"])

        return {
            "passed_count": passed_count,
            "pass@1": passed_count / len(results) if results else 0
        }

    def _format_signature(self, function_name: str, prompt: str) -> str:
        """从提示中提取函数签名"""
        # 尝试找到示例调用或签名描述
        signature = ""

        # 搜索包含函数名的行
        lines = prompt.split("\n")
        for line in lines:
            if function_name in line and "(" in line and ")" in line:
                # 提取括号内的内容
                start = line.find(function_name) + len(function_name)
                signature = line[start:].strip()
                if signature.startswith("("):
                    end = signature.find(")") + 1
                    if end > 0:
                        signature = signature[:end]
                        break

        if not signature:
            # 没有找到明确的签名，返回空括号
            signature = "()"

        return signature
