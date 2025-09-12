# core/collaboration.py
from typing import List, Dict, Any
from agents.base_agent import Agent


class CollaborationManager():
    """
    管理Agent协作。
    不要搞所有基于置信度的修正循环。
    """
    async def execute_plan(self,
                           plan: Dict[str, Any],
                           agents: List[Agent],
                           task_description: str) -> Dict[str, Any]:
        context = {
            "task_description": task_description,
            "agents": {agent.name: agent for agent in agents}
        }

        final_result = {"output": None, "steps": [], "context": {}}
        collaboration_history = ""
        last_output = "No steps were executed."
        plan_steps = plan.get("steps", [])

        for i, step in enumerate(plan_steps):
            agent_name = step["agent"]
            action = step["action"]

            print(f"\n--- [Collaboration] Executing Step {i + 1} ---")
            print(f"  Agent: {agent_name}")
            print(f"  Action: {action}")

            agent = context["agents"].get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found")

            prompt = self._format_prompt_with_history(
                task_description,
                collaboration_history,
                agent,
                action
            )

            # 直接执行，不再有修正循环
            step_output_text = await agent.generate(prompt)
            print(f"  Step Output (truncated): {step_output_text[:150]}...")

            collaboration_history += f"--- Step {i + 1}: Agent '{agent.name}' ({action}) ---\n"
            collaboration_history += f"{step_output_text}\n\n"

            last_output = step_output_text
            final_result["steps"].append({"agent": agent_name, "action": action, "output": step_output_text})

        final_result["output"] = last_output
        final_result["context"] = {k: v for k, v in context.items() if k != "agents"}

        return final_result

    def _format_prompt_with_history(self, task_description: str, history: str, agent: Agent, action: str) -> str:
        """为Agent构建包含完整上下文的Prompt。"""
        prompt = f"**Original Task:**\n{task_description}\n\n"

        if history:
            prompt += f"**Collaboration History (Previous Steps):**\n{history}\n"
        else:
            prompt += "**Collaboration History (Previous Steps):**\nThis is the first step. There is no history yet.\n\n"

        prompt += f"**Your Current Task:**\n"
        prompt += f"You are agent '{agent.name}'. Your role is: {agent.role}.\n"
        prompt += f"Your current action is: '{action}'.\n"
        prompt += "Based on the original task and the full collaboration history, please perform your action. Provide a clear, comprehensive response."

        return prompt