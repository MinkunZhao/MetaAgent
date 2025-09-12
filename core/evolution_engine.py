# core/evolution_engine.py
import re
from typing import Dict, Any, List
import json
from agents.base_agent import Agent
from .agent_factory import AgentFactory
from utils.prompt_utils import load_prompt_template
from utils.json_utils import extract_and_parse_json


class EvolutionEngine:
    """
    自我进化引擎，负责改进Agent模板和协作流程
    """
    def __init__(self, config: Dict, agent_factory: AgentFactory):
        self.config = config
        self.agent_factory = agent_factory
        self.evolution_agent = Agent(
            name="EvolutionAgent",
            system_prompt="You are an AI system optimization specialist...", # (不变)
            config=config
        )

    async def evolve_from_correction(self, task_analysis: Dict, root_cause: str, abstract_takeaways: List[str]):
        """基于对错误的深刻分析进行系统进化。"""
        print(f"  Analyzing correction takeaways for evolution...")

        prompt = load_prompt_template("improve_system_from_correction").format(
            task_analysis_json=json.dumps(task_analysis, indent=2),
            root_cause=root_cause,
            abstract_takeaways_json=json.dumps(abstract_takeaways, indent=2)
        )

        response_text = await self.evolution_agent.generate(prompt)

        # 简单的json提取
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            try:
                improvement_plan = json.loads(match.group(0))
            except json.JSONDecodeError:
                improvement_plan = None
        else:
            improvement_plan = None

        if not improvement_plan or "element_to_improve" not in improvement_plan:
            print("  FAILURE: Could not generate a valid improvement plan from the correction analysis.")
            return

        print("  Generated improvement plan from correction analysis:")
        print(json.dumps(improvement_plan, indent=2))

        if improvement_plan.get("type") == "agent_template":
            await self._evolve_agent_template(
                agent_type=improvement_plan.get("element_to_improve"),
                suggestions=improvement_plan.get("suggestions", []),
                context_info={"root_cause": root_cause, "takeaways": abstract_takeaways}
            )

    async def _evolve_agent_template(self,
                                     agent_type: str,
                                     suggestions: List[str],
                                     context_info: Dict):
        """改进Agent模板"""
        if not agent_type:
            print("  FAILURE: Cannot evolve agent template without an agent_type.")
            return

        print(f"  Attempting to evolve agent template: {agent_type}")
        current_template = self.agent_factory.agent_templates.get(agent_type, {
            "system_prompt": f"You are a helpful {agent_type} assistant."
        })

        prompt = load_prompt_template("improve_agent_template").format(
            agent_type=agent_type,
            current_template=json.dumps(current_template, indent=2),
            context_info=json.dumps(context_info, indent=2),
            suggestions=json.dumps(suggestions, indent=2)
        )

        response_dict = await self.evolution_agent.generate(prompt)
        response_text = response_dict.get("response", "")
        improved_template = extract_and_parse_json(response_text)

        if improved_template and "system_prompt" in improved_template:
            # 稳健性检查：确保新prompt不是空的或过短
            new_prompt = improved_template["system_prompt"]
            if isinstance(new_prompt, str) and len(new_prompt) > 20:
                await self.agent_factory.save_agent_template(agent_type, improved_template)
                print(f"  SUCCESS: Evolved and saved new template for '{agent_type}'.")
            else:
                print(f"  FAILURE: Proposed new template for '{agent_type}' was invalid or too short. No changes made.")
        else:
            print(f"  FAILURE: Could not parse a valid improved template for '{agent_type}'. No changes were made.")