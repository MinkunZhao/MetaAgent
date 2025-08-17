# core/evolution_engine.py
from typing import Dict, Any, List
import json
import os
from agents.base_agent import Agent
from .agent_factory import AgentFactory
from utils.prompt_utils import load_prompt_template
from utils.json_utils import extract_and_parse_json
from memory.experience_store import ExperienceStore


class EvolutionEngine:
    """
    自我进化引擎，负责改进Agent模板和协作流程
    """

    def __init__(self, config: Dict[str, Any], agent_factory: AgentFactory):
        """初始化进化引擎"""
        self.config = config
        self.agent_factory = agent_factory
        self.experience_store = ExperienceStore()
        self.evolution_agent = Agent(
            name="EvolutionAgent",
            system_prompt="You are an AI system optimization specialist focused on improving multi-agent systems through thoughtful, data-driven analysis and redesign.",
            config=config
        )

    async def evolve_from_single_task(self,
                                      task_analysis: Dict[str, Any],
                                      result: Dict[str, Any],
                                      evaluation: Dict[str, Any]) -> None:
        """
        基于单次任务执行结果进行系统进化 (Intra-test-time / a single Inter-test-time evolution)
        """
        print("  Analyzing single task performance for immediate evolution...")
        # 1. 分析性能并确定需要改进的地方
        improvement_areas = await self._identify_improvement_areas(
            task_analysis, result, evaluation
        )

        # 2. 针对每个需要改进的区域执行特定的进化
        for area in improvement_areas:
            # 确保 area 是一个字典
            if not isinstance(area, dict):
                print(f"  Skipping invalid improvement area item: {area}")
                continue

            if area.get("type") == "agent_template":
                await self._evolve_agent_template(
                    agent_type=area.get("specific_element_to_improve"),
                    suggestions=area.get("suggestions", []),
                    context_info={
                        "task_analysis": task_analysis,
                        "result": result
                    }
                )

    async def evolve_from_experience_store(self):
        """
        从经验库中综合学习并进化 (Inter-test-time evolution)
        """
        print("  Synthesizing experiences from store for long-term evolution...")
        experiences = await self.experience_store.load_all_experiences()
        if len(experiences) < 3:  # 至少需要几条经验才能进行有意义的综合
            print("  Not enough experiences to conduct a synthesis-based evolution.")
            return

        prompt = load_prompt_template("synthesize_experiences").format(
            experiences_json=json.dumps(experiences[-10:], indent=2)  # 使用最近10条经验
        )
        response = await self.evolution_agent.generate(prompt)

        improvement_plan = extract_and_parse_json(response)

        # 【BUG 修复】如果LLM返回单个对象而不是数组，将其包装在列表中
        if improvement_plan and isinstance(improvement_plan, dict):
            improvement_plan = [improvement_plan]

        if not improvement_plan or not isinstance(improvement_plan, list):
            print("  Could not generate a valid improvement plan from experience synthesis.")
            return

        print("  Generated improvement plan from experience synthesis:")
        print(json.dumps(improvement_plan, indent=2))

        for area in improvement_plan:
            # 确保 area 是一个字典
            if not isinstance(area, dict):
                print(f"  Skipping invalid improvement plan item: {area}")
                continue

            if area.get("type") == "agent_template":
                await self._evolve_agent_template(
                    agent_type=area.get("specific_element_to_improve"),
                    suggestions=area.get("suggestions", []),
                    context_info={
                        "synthesis_summary": area.get("reasoning", "")
                    }
                )

    async def _identify_improvement_areas(self,
                                          task_analysis: Dict[str, Any],
                                          result: Dict[str, Any],
                                          evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别需要改进的区域"""
        prompt = load_prompt_template("identify_improvements").format(
            task_analysis=json.dumps(task_analysis, indent=2),
            result=json.dumps(result, indent=2),
            evaluation=json.dumps(evaluation, indent=2)
        )

        response = await self.evolution_agent.generate(prompt)
        parsed_json = extract_and_parse_json(response)

        # 【BUG 修复】如果LLM返回单个对象而不是数组，将其包装在列表中
        if parsed_json:
            if isinstance(parsed_json, dict):
                return [parsed_json]
            return parsed_json

        print("警告: 识别改进点时未能解析JSON，使用默认值。")
        agent_type_to_improve = task_analysis.get("task_type", "executor")
        if "math" in agent_type_to_improve:
            agent_type_to_improve = "hard_math_agent"
        elif "code" in agent_type_to_improve:
            agent_type_to_improve = "code_generator"

        return [
            {
                "type": "agent_template",
                "specific_element_to_improve": agent_type_to_improve,
                "suggestions": ["Improve system prompt clarity based on failure points.",
                                "Add more specialized knowledge or examples to the prompt."]
            }
        ]

    async def _evolve_agent_template(self,
                                     agent_type: str,
                                     suggestions: List[str],
                                     context_info: Dict[str, Any]) -> None:
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

        response = await self.evolution_agent.generate(prompt)
        improved_template = extract_and_parse_json(response)

        if improved_template and "system_prompt" in improved_template:
            await self.agent_factory.save_agent_template(agent_type, improved_template)
            print(f"  SUCCESS: Evolved and saved new template for '{agent_type}'.")
        else:
            print(f"  FAILURE: Could not parse a valid improved template for '{agent_type}'. No changes were made.")