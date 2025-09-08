# core/meta_agent.py
from typing import List, Dict, Any
import os
import json
from agents.base_agent import Agent
from .agent_factory import AgentFactory
from .collaboration import CollaborationManager
from .evolution_engine import EvolutionEngine
from utils.prompt_utils import load_prompt_template
from utils.json_utils import extract_and_parse_json
# from memory.knowledge_base import KnowledgeBase
# from memory.experience_store import ExperienceStore


class MetaAgent(Agent):
    """
    Meta Agent负责生成和协调其他Agent来完成任务，并具有自我进化能力
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化Meta Agent"""
        super().__init__(
            name="MetaAgent",
            system_prompt=load_prompt_template("meta_agent_system"),
            config=config
        )
        self.config = config
        self.agent_factory = AgentFactory(config)
        self.collaboration_manager = CollaborationManager()
        self.evolution_engine = EvolutionEngine(config, self.agent_factory)
        # self.knowledge_base = KnowledgeBase()
        # self.experience_store = ExperienceStore()
        self.task_counter = 0

    # NEW METHOD: A dedicated internal generator for structured JSON output
    async def _generate_structured_json(self, prompt: str) -> Any:
        """
        一个专用于生成纯JSON输出的内部方法，不触发自我评估。
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        # Directly call the api_manager for a clean response
        response_text = await self.api_manager.generate_chat_completion(messages)
        return extract_and_parse_json(response_text)

    async def handle_task(self, task_description: str, allow_evolution: bool = True) -> Dict[str, Any]:
        """
        处理用户任务
        """
        self.task_counter += 1

        print("\n--- [MetaAgent] Analyzing Task ---")
        task_analysis = await self._analyze_task(task_description)
        print(json.dumps(task_analysis, indent=2, ensure_ascii=False))

        print("\n--- [MetaAgent] Determining Required Agents ---")
        required_agents = await self._determine_required_agents(task_analysis)
        print(json.dumps(required_agents, indent=2, ensure_ascii=False))

        agents = await self.agent_factory.create_agents(required_agents)
        print("\n--- [MetaAgent] Created Sub-Agents ---")
        for agent in agents:
            print(f"- Name: {agent.name}, Type: {agent.type}, Role: {agent.role}")

        print("\n--- [MetaAgent] Designing Collaboration Plan ---")
        collaboration_plan = await self._design_collaboration(task_analysis, agents)
        print(json.dumps(collaboration_plan, indent=2, ensure_ascii=False))

        print("\n--- [MetaAgent] Starting Collaboration ---")
        result = await self.collaboration_manager.execute_plan(
            collaboration_plan,
            agents,
            task_description
        )

        evaluation = await self._evaluate_result(result, task_description)

        # await self._update_experience(task_analysis, agents, result, evaluation)

        if allow_evolution:
            if evaluation.get('should_evolve', False):
                print("\n--- [MetaAgent] Triggering Intra-task Self-Evolution ---")
                await self.evolution_engine.evolve_from_single_task(
                    task_analysis,
                    result,
                    evaluation
                )

            # if self.task_counter % 5 == 0:
            #     print("\n--- [MetaAgent] Triggering Inter-task (Experience-based) Self-Evolution ---")
            #     await self.evolution_engine.evolve_from_experience_store()

        return result

    async def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        """分析任务"""
        prompt = load_prompt_template("task_analysis").format(
            task_description=task_description
        )
        parsed_json = await self._generate_structured_json(prompt)

        if parsed_json:
            return parsed_json

        print("警告: 任务分析未能解析JSON，使用智能回退机制。")
        # 更智能的回退
        desc_lower = task_description.lower()
        math_keywords = ["math", "aime", "geometry", "algebra", "combinatorics", "number theory", "calculate",
                         "find the value"]
        if any(keyword in desc_lower for keyword in math_keywords):
            print("  检测到数学相关关键词，回退到高复杂度数学任务类型。")
            return {
                "task_type": "high_complexity_math", "complexity": "high",
                "key_requirements": ["solve the math problem accurately", "provide step-by-step reasoning"],
                "suggested_approach": "Use specialized math agents and review the solution."
            }
        return {
            "task_type": "unknown", "complexity": "medium",
            "key_requirements": ["complete the task"],
            "suggested_approach": "general problem solving"
        }

    async def _determine_required_agents(self, task_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据任务分析确定需要哪些Agent"""
        task_type = task_analysis.get("task_type", "").lower()
        complexity = task_analysis.get("complexity", "")

        # MODIFIED: More robust check for math-related tasks
        math_related_keywords = ["math", "combinatorics", "geometry", "algebra"]
        is_math_task = any(keyword in task_type for keyword in math_related_keywords)

        if is_math_task and complexity == "high":
            print("检测到高难度数学任务，使用专门的hard_math_agent和math_reviewer。")
            return [
                {
                    "type": "hard_math_agent",
                    "name": "HardMathSolverAgent",
                    "role": "Execute the plan to solve the complex math problem",
                    "custom_prompt": self.agent_factory.agent_templates.get("hard_math_agent", {}).get("system_prompt")
                },
                {
                    # MODIFIED: Use the correct math_reviewer
                    "type": "math_reviewer",
                    "name": "MathReviewerAgent",
                    "role": "Review the mathematical solution and final answer for correctness",
                    "custom_prompt": self.agent_factory.agent_templates.get("math_reviewer", {}).get("system_prompt")
                }
            ]

        prompt = load_prompt_template("determine_agents").format(
            task_analysis=json.dumps(task_analysis, indent=2)
        )
        parsed_json = await self._generate_structured_json(prompt)
        if parsed_json:
            return parsed_json
        print("警告: 代理决策未能解析JSON，使用默认值。")
        return [
            {"type": "planner", "name": "PlannerAgent", "role": "Plan the approach",
             "custom_prompt": "You are a planning agent."},
            {"type": "executor", "name": "ExecutorAgent", "role": "Execute the plan",
             "custom_prompt": "You are an execution agent."}
        ]

    async def _design_collaboration(self,
                                    task_analysis: Dict[str, Any],
                                    agents: List[Agent]) -> Dict[str, Any]:
        """设计协作流程"""
        agent_info = [{"name": agent.name, "role": agent.role, "type": agent.type} for agent in agents]

        # If there's no planner, the first agent should directly execute.
        has_planner = any(a.type == 'planner' for a in agents)
        is_math_task = "math" in task_analysis.get("task_type", "")

        # For high-complexity math, a direct execution is better than a generic plan.
        if not has_planner or is_math_task:
            executor = next((a.name for a in agents if a.type in ['hard_math_agent', 'executor']), agents[0].name)
            return {"steps": [{"agent": executor, "action": "execute", "input": "task_description"}],
                    "final_output": "last_output"}

        prompt = load_prompt_template("design_collaboration").format(
            task_analysis=json.dumps(task_analysis, indent=2),
            agents=json.dumps(agent_info, indent=2)
        )
        # MODIFIED: Use the new internal generator
        parsed_json = await self._generate_structured_json(prompt)
        if parsed_json:
            return parsed_json
        print("警告: 协作设计未能解析JSON，使用默认流程。")
        planner = next((a.name for a in agents if a.type == 'planner'), agents[0].name)
        executor = next((a.name for a in agents if a.type == 'executor'), agents[-1].name)
        return {
            "steps": [
                {"agent": planner, "action": "plan", "input": "task_description"},
                {"agent": executor, "action": "execute", "input": "previous_output"},
            ],
            "final_output": "last_output"
        }

    async def _evaluate_result(self,
                               result: Dict[str, Any],
                               task_description: str) -> Dict[str, Any]:
        """评估任务结果"""
        prompt = load_prompt_template("evaluate_result").format(
            task_description=task_description,
            result=json.dumps(result, indent=2, default=str)
        )
        # MODIFIED: Use the new internal generator
        parsed_json = await self._generate_structured_json(prompt)
        if parsed_json and isinstance(parsed_json, dict):
            evaluation = parsed_json
            evaluation["should_evolve"] = evaluation.get("score", 0) < 0.7
            return evaluation
        print("警告: 结果评估未能解析JSON，使用默认值。")
        return {
            "score": 0.5, "strengths": [],
            "weaknesses": ["Evaluation response was not valid JSON."],
            "should_evolve": True
        }

    async def _update_experience(self,
                                 task_analysis: Dict[str, Any],
                                 agents: List[Agent],
                                 result: Dict[str, Any],
                                 evaluation: Dict[str, Any]) -> None:
        """更新经验库"""
        agent_specs = [{"name": a.name, "type": a.type, "system_prompt": a.system_prompt} for a in agents]
        experience = {
            "task_analysis": task_analysis,
            "agents_used": agent_specs,
            "result_trajectory": result,
            "evaluation": evaluation
        }
        await self.experience_store.store_experience(experience)