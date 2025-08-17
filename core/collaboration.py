# core/collaboration.py
from typing import List, Dict, Any
from agents.base_agent import Agent
import asyncio
import json


class CollaborationManager():
    """
    管理Agent之间的协作流程, 支持迭代修正循环
    """
    MAX_REFINE_LOOPS = 2  # 设置最大修正次数，防止无限循环

    async def execute_plan(self,
                           plan: Dict[str, Any],
                           agents: List[Agent],
                           task_description: str) -> Dict[str, Any]:
        """
        执行协作计划
        """
        context = {
            "task_description": task_description,
            "agents": {agent.name: agent for agent in agents}
        }

        step_outputs = {}
        final_result = {"output": None, "steps": [], "context": {}}

        for i, step in enumerate(plan["steps"]):
            agent_name = step["agent"]
            action = step["action"]
            input_source = step["input"]

            print(f"\n--- [Collaboration] Executing Step {i + 1} ---")
            print(f"  Agent: {agent_name}")
            print(f"  Action: {action}")

            # 获取输入
            if input_source == "task_description":
                input_content = task_description
            elif input_source == "previous_output" and i > 0:
                input_content = step_outputs[i - 1]
            else:
                input_content = step_outputs.get(input_source, "")

            agent = context["agents"].get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found")

            # 检查是否是需要修正的特殊动作
            if action == "review_and_refine":
                result = await self._execute_refinement_loop(agent, agents, input_content, context)
            else:
                result = await self._execute_action(agent, action, input_content, context)

            print(f"  Step {i + 1} Output (truncated): {str(result)[:250]}...")
            step_outputs[i] = result
            final_result["steps"].append({"agent": agent_name, "action": action, "output": result})

        # 确定最终输出
        final_output_source = plan.get("final_output", "last_output")
        if final_output_source == "last_output" and len(plan["steps"]) > 0:
            final_result["output"] = step_outputs[len(plan["steps"]) - 1]
        else:
            final_result["output"] = step_outputs.get(final_output_source, "")

        final_result["context"] = {k: v for k, v in context.items() if k != "agents"}
        return final_result

    async def _execute_refinement_loop(self, reviewer: Agent, agents: List[Agent], initial_solution: str,
                                       context: Dict[str, Any]) -> str:
        """执行自我反思和修正的循环 (Intra-test-time evolution)"""
        current_solution = initial_solution

        for i in range(self.MAX_REFINE_LOOPS):
            print(f"    [Refinement Loop {i + 1}/{self.MAX_REFINE_LOOPS}]")

            # 1. 评审 (Review)
            review_prompt = f"Please review the following solution. If it is correct and complete, respond with 'CORRECT'. Otherwise, provide specific, actionable feedback for improvement.\n\nSolution:\n{current_solution}"
            feedback = await reviewer.generate(review_prompt)
            print(f"    Reviewer Feedback: {feedback[:150]}...")

            if "CORRECT" in feedback.upper():
                print("    Solution deemed correct. Exiting refinement loop.")
                return current_solution

            # 2. 修正 (Refine) - 寻找一个执行者或代码生成者来修正
            refiner = next(
                (agent for agent in agents if agent.type in ['executor', 'code_generator', 'hard_math_agent']), None)
            if not refiner:
                print("    No suitable refiner agent found. Returning last solution.")
                return current_solution

            print(f"    Refining solution with {refiner.name}...")
            refine_prompt = f"The previous solution was reviewed and needs improvement. Please generate a new, corrected solution based on the following feedback.\n\nOriginal Solution:\n{current_solution}\n\nFeedback:\n{feedback}\n\nProvide only the complete, new solution."

            current_solution = await refiner.generate(refine_prompt)

        print("    Max refinement loops reached. Returning the latest solution.")
        return current_solution

    async def _execute_action(self,
                              agent: Agent,
                              action: str,
                              input_content: str,
                              context: Dict[str, Any]) -> str:
        """执行特定的操作"""
        prompt_map = {
            "plan": f"Create a detailed plan to solve the following task:\n\n{input_content}",
            "execute": f"Implement a solution for the following task, based on this plan:\n\n{input_content}",
            "review": f"Review the following solution critically:\n\n{input_content}",
            "code": f"Write code to solve the following problem:\n\n{input_content}",
            "test": f"Write test cases for the following code:\n\n{input_content}",
            "debug": f"Debug the following code and fix any issues:\n\n{input_content}",
            "improve": f"Improve the following solution:\n\n{input_content}",
        }

        prompt = prompt_map.get(action, input_content)  # 默认为直接生成
        return await agent.generate(prompt)