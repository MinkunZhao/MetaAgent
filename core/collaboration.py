# core/collaboration.py
from typing import List, Dict, Any
from agents.base_agent import Agent
import asyncio


class CollaborationManager():
    """
    管理Agent之间的协作流程, 支持基于置信度的动态迭代修正循环。
    """
    MAX_REFINE_LOOPS = 2
    CONFIDENCE_THRESHOLD = 0.75  # 低于此阈值将触发审阅

    async def execute_plan(self,
                           plan: Dict[str, Any],
                           agents: List[Agent],
                           task_description: str) -> Dict[str, Any]:
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
                input_content = step_outputs[i - 1]["response"]  # 只传递主响应
            else:
                input_content = step_outputs.get(input_source, {}).get("response", "")

            agent = context["agents"].get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found")

            # 执行基础动作
            result_dict = await self._execute_action(agent, action, input_content, context)

            print(f"  Step {i + 1} Initial Output (truncated): {str(result_dict['response'])[:150]}...")
            print(f"  Agent Confidence: {result_dict['confidence']:.2f} ({result_dict['reasoning']})")

            # 基于置信度的动态修正循环 (SE-Agent & Confidence)
            # 主要对执行或编码步骤进行检查
            if action in ["execute", "code", "improve"] and result_dict['confidence'] < self.CONFIDENCE_THRESHOLD:
                print(f"  Confidence below {self.CONFIDENCE_THRESHOLD}. Triggering refinement loop...")
                refined_result_dict = await self._execute_refinement_loop(
                    initial_solution_dict=result_dict,
                    agents=agents,
                    context=context
                )
                result_dict = refined_result_dict  # 使用修正后的结果

            step_outputs[i] = result_dict
            final_result["steps"].append({"agent": agent_name, "action": action, "output": result_dict})

        # 确定最终输出
        final_output_source = plan.get("final_output", "last_output")
        if final_output_source == "last_output" and len(plan["steps"]) > 0:
            final_result["output"] = step_outputs[len(plan["steps"]) - 1]["response"]
        else:
            final_result["output"] = step_outputs.get(final_output_source, {}).get("response", "")

        final_result["context"] = {k: v for k, v in context.items() if k != "agents"}
        return final_result

    async def _execute_refinement_loop(self, initial_solution_dict: Dict, agents: List[Agent],
                                       context: Dict[str, Any]) -> Dict[str, Any]:
        """执行自我反思和修正的循环"""
        current_solution_dict = initial_solution_dict

        # 寻找审阅者和修正者
        reviewer = next((agent for agent in agents if agent.type in ['reviewer', 'code_reviewer']), None)
        refiner = next((agent for agent in agents if agent.type in ['executor', 'code_generator', 'hard_math_agent']),
                       None)

        if not reviewer or not refiner:
            print("    Reviewer or Refiner agent not found. Skipping refinement.")
            return current_solution_dict

        for i in range(self.MAX_REFINE_LOOPS):
            print(f"    [Refinement Loop {i + 1}/{self.MAX_REFINE_LOOPS}]")
            current_solution_text = current_solution_dict["response"]

            # 1. 审阅 (Review)
            review_prompt = f"The following solution was generated with low confidence ({current_solution_dict['confidence']:.2f}, Reason: {current_solution_dict['reasoning']}). Please review it. If it is correct, respond with 'CORRECT'. Otherwise, provide specific, actionable feedback for improvement.\n\nSolution:\n{current_solution_text}"
            review_result_dict = await reviewer.generate(review_prompt)
            feedback = review_result_dict["response"]
            print(f"    Reviewer Feedback: {feedback[:150]}...")

            if "CORRECT" in feedback.upper():
                print("    Solution deemed correct. Exiting refinement loop.")
                return current_solution_dict

            # 2. 修正 (Refine)
            print(f"    Refining solution with {refiner.name}...")
            refine_prompt = f"The previous solution was reviewed and needs improvement. Please generate a new, corrected solution based on the following feedback.\n\nOriginal Solution:\n{current_solution_text}\n\nFeedback:\n{feedback}\n\nProvide only the complete, new solution."
            current_solution_dict = await refiner.generate(refine_prompt)
            print(f"    New solution generated with confidence: {current_solution_dict['confidence']:.2f}")

        print("    Max refinement loops reached. Returning the latest solution.")
        return current_solution_dict

    async def _execute_action(self,
                              agent: Agent,
                              action: str,
                              input_content: str,
                              context: Dict[str, Any]) -> Dict[str, Any]:
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
        prompt = prompt_map.get(action, input_content)
        return await agent.generate(prompt)