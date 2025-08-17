# utils/evaluation.py
from typing import Dict, Any, List, Optional
import json
import subprocess
import os
import tempfile


class CodeEvaluator:
    """
    代码评估工具，用于评估生成的代码质量
    """

    async def evaluate_code(self,
                            code: str,
                            language: str,
                            test_cases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """评估代码的正确性和质量"""
        results = {
            "syntax_valid": False,
            "execution_results": [],
            "passed_tests": 0,
            "total_tests": 0,
            "errors": []
        }

        # 检查语法
        syntax_result = await self._check_syntax(code, language)
        results["syntax_valid"] = syntax_result["valid"]
        if not syntax_result["valid"]:
            results["errors"].append(syntax_result["error"])
            return results

        # 如果没有测试用例，只返回语法检查结果
        if not test_cases:
            return results

        # 执行测试用例
        results["total_tests"] = len(test_cases)

        for i, test_case in enumerate(test_cases):
            test_result = await self._execute_test(code, language, test_case)
            results["execution_results"].append(test_result)

            if test_result["passed"]:
                results["passed_tests"] += 1
            else:
                results["errors"].append(f"Test case {i + 1} failed: {test_result['error']}")

        return results

    async def _check_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """检查代码语法"""
        result = {"valid": False, "error": ""}

        with tempfile.NamedTemporaryFile(suffix=self._get_extension(language), mode="w", delete=False) as temp:
            temp.write(code)
            temp_path = temp.name

        try:
            if language.lower() == "python":
                # Python语法检查
                process = subprocess.run(
                    ["python", "-m", "py_compile", temp_path],
                    capture_output=True,
                    text=True
                )

                if process.returncode != 0:
                    result["error"] = process.stderr
                else:
                    result["valid"] = True

            elif language.lower() == "javascript":
                # JavaScript语法检查
                process = subprocess.run(
                    ["node", "--check", temp_path],
                    capture_output=True,
                    text=True
                )

                if process.returncode != 0:
                    result["error"] = process.stderr
                else:
                    result["valid"] = True
            else:
                # 其他语言暂不支持
                result["valid"] = True
                result["error"] = f"Syntax checking for {language} is not implemented"
        except Exception as e:
            result["error"] = str(e)
        finally:
            os.unlink(temp_path)

        return result

    async def _execute_test(self, code: str, language: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """执行测试用例"""
        result = {
            "input": test_case.get("input", ""),
            "expected_output": test_case.get("expected_output", ""),
            "actual_output": "",
            "passed": False,
            "error": ""
        }

        with tempfile.NamedTemporaryFile(suffix=self._get_extension(language), mode="w", delete=False) as temp:
            # 组合代码和测试
            if language.lower() == "python":
                combined_code = f"{code}\n\n# Test case\n{test_case.get('test_code', '')}"
            elif language.lower() == "javascript":
                combined_code = f"{code}\n\n// Test case\n{test_case.get('test_code', '')}"
            else:
                combined_code = code

            temp.write(combined_code)
            temp_path = temp.name

        try:
            if language.lower() == "python":
                # 执行Python代码
                process = subprocess.run(
                    ["python", temp_path],
                    input=test_case.get("input", ""),
                    capture_output=True,
                    text=True
                )

                if process.returncode != 0:
                    result["error"] = process.stderr
                else:
                    result["actual_output"] = process.stdout.strip()

            elif language.lower() == "javascript":
                # 执行JavaScript代码
                process = subprocess.run(
                    ["node", temp_path],
                    input=test_case.get("input", ""),
                    capture_output=True,
                    text=True
                )

                if process.returncode != 0:
                    result["error"] = process.stderr
                else:
                    result["actual_output"] = process.stdout.strip()
            else:
                # 其他语言暂不支持
                result["error"] = f"Execution for {language} is not implemented"
        except Exception as e:
            result["error"] = str(e)
        finally:
            os.unlink(temp_path)

        # 检查结果是否与预期相符
        expected = test_case.get("expected_output", "").strip()
        actual = result["actual_output"].strip()

        if expected == actual:
            result["passed"] = True
        elif test_case.get("comparison_type") == "contains" and expected in actual:
            result["passed"] = True
        elif test_case.get("custom_validator"):
            # 如果有自定义验证函数，尝试执行
            try:
                validator_code = test_case["custom_validator"]
                with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as vtemp:
                    vtemp.write(f"""
def validate(expected, actual):
{validator_code}

result = validate({repr(expected)}, {repr(actual)})
print(result)
""")
                    vtemp_path = vtemp.name

                validator_process = subprocess.run(
                    ["python", vtemp_path],
                    capture_output=True,
                    text=True
                )

                if validator_process.stdout.strip().lower() == "true":
                    result["passed"] = True

                os.unlink(vtemp_path)
            except Exception as e:
                result["error"] += f"\nValidator error: {str(e)}"

        return result

    def _get_extension(self, language: str) -> str:
        """获取语言对应的文件扩展名"""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "java": ".java",
            "c": ".c",
            "cpp": ".cpp",
            "go": ".go",
            "ruby": ".rb",
            "php": ".php"
        }
        return extensions.get(language.lower(), ".txt")
