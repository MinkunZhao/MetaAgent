# core/meta_agent.py
from typing import List, Dict, Any
import os
import json
# from mcp_agent.agents.agent import Agent
from agents.base_agent import Agent  # 更新导入路径
from .agent_factory import AgentFactory
from .collaboration import CollaborationManager
from .evolution_engine import EvolutionEngine
from utils.prompt_utils import load_prompt_template
from utils.json_utils import extract_and_parse_json
from memory.knowledge_base import KnowledgeBase
from memory.experience_store import ExperienceStore



class MetaAgent(Agent):
    """
    Meta Agent负责生成和协调其他Agent来完成任务，并具有自我进化能力
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化Meta Agent"""
        super().__init__(
            name="MetaAgent",
            system_prompt=load_prompt_template("meta_agent_system"),
            config=config  # 添加配置传递
        )
        # super().__init__(
        #     name="MetaAgent",
        #     system_prompt=load_prompt_template("meta_agent_system")
        # )
        self.config = config
        self.agent_factory = AgentFactory(config)
        self.collaboration_manager = CollaborationManager()
        self.evolution_engine = EvolutionEngine(config, self.agent_factory)
        self.knowledge_base = KnowledgeBase()
        self.experience_store = ExperienceStore()
        self.task_counter = 0

    async def handle_task(self, task_description: str, allow_evolution: bool = True) -> Dict[str, Any]:
        """
        处理用户任务

        Args:
            task_description: 任务的描述
            allow_evolution: 是否允许在该任务后触发进化机制
        """
        self.task_counter += 1

        # 1. 分析任务
        print("\n--- [MetaAgent] Analyzing Task ---")
        task_analysis = await self._analyze_task(task_description)
        print(json.dumps(task_analysis, indent=2, ensure_ascii=False))

        # 2. 确定所需的Agent类型和数量
        print("\n--- [MetaAgent] Determining Required Agents ---")
        required_agents = await self._determine_required_agents(task_analysis)
        print(json.dumps(required_agents, indent=2, ensure_ascii=False))

        # 3. 生成或检索Agent
        agents = await self.agent_factory.create_agents(required_agents)
        print("\n--- [MetaAgent] Created Sub-Agents ---")
        for agent in agents:
            print(f"- Name: {agent.name}, Type: {agent.type}, Role: {agent.role}")

        # 4. 设计协作流程
        print("\n--- [MetaAgent] Designing Collaboration Plan ---")
        collaboration_plan = await self._design_collaboration(task_analysis, agents)
        print(json.dumps(collaboration_plan, indent=2, ensure_ascii=False))

        # 5. 执行协作流程
        print("\n--- [MetaAgent] Starting Collaboration ---")
        result = await self.collaboration_manager.execute_plan(
            collaboration_plan,
            agents,
            task_description
        )

        # 6. 评估结果
        evaluation = await self._evaluate_result(result, task_description)

        # 7. 更新经验和知识
        await self._update_experience(task_analysis, agents, result, evaluation)

        # 8. 触发自我进化（如果需要且被允许）
        if allow_evolution:
            if evaluation.get('should_evolve', False):
                print("\n--- [MetaAgent] Triggering Intra-task Self-Evolution ---")
                await self.evolution_engine.evolve_from_single_task(
                    task_analysis,
                    result,
                    evaluation
                )

            # 每隔5个任务，触发一次基于经验库的宏观进化
            if self.task_counter % 5 == 0:
                print("\n--- [MetaAgent] Triggering Inter-task (Experience-based) Self-Evolution ---")
                await self.evolution_engine.evolve_from_experience_store()

        return result

    async def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        """分析任务，确定任务类型、难度和关键要求"""
        prompt = load_prompt_template("task_analysis").format(
            task_description=task_description
        )
        response = await self.generate(prompt)
        # try:
        #     return json.loads(response)
        # except:
        #     # 如果返回的不是有效的JSON，进行后处理
        #     return {
        #         "task_type": "unknown",
        #         "complexity": "medium",
        #         "key_requirements": ["complete the task"],
        #         "suggested_approach": "general problem solving"
        #     }
        parsed_json = extract_and_parse_json(response)
        if parsed_json:
            return parsed_json
        print("警告: 任务分析未能解析JSON，使用默认值。")
        return {
            "task_type": "unknown",
            "complexity": "medium",
            "key_requirements": ["complete the task"],
            "suggested_approach": "general problem solving"
        }

    async def _determine_required_agents(self, task_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据任务分析确定需要哪些Agent"""
        task_type = task_analysis.get("task_type", "unknown")
        if "math" in task_type.lower() and task_analysis.get("complexity") == "high":
            print("检测到高难度数学任务，使用专门的hard_math_agent。")
            return [
                {"type": "planner", "name": "MathPlannerAgent", "role": "Plan the mathematical solving steps"},
                {"type": "hard_math_agent", "name": "HardMathSolverAgent",
                 "role": "Execute the plan to solve the complex math problem"},
                {"type": "reviewer", "name": "MathReviewerAgent",
                 "role": "Review the mathematical solution and final answer for correctness"}
            ]
        prompt = load_prompt_template("determine_agents").format(
            task_analysis=json.dumps(task_analysis, indent=2)
        )
        response = await self.generate(prompt)
        # try:
        #     return json.loads(response)
        # except:
        #     # 默认返回
        #     return [
        #         {"type": "planner", "role": "Plan the approach"},
        #         {"type": "executor", "role": "Execute the plan"},
        #         # {"type": "reviewer", "role": "Review the result"}
        #     ]
        parsed_json = extract_and_parse_json(response)
        if parsed_json:
            return parsed_json
        print("警告: 代理决策未能解析JSON，使用默认值。")
        return [
            {"type": "planner", "name": "PlannerAgent", "role": "Plan the approach"},
            {"type": "executor", "name": "ExecutorAgent", "role": "Execute the plan"}
        ]

    async def _design_collaboration(self,
                                    task_analysis: Dict[str, Any],
                                    agents: List[Agent]) -> Dict[str, Any]:
        """设计Agent之间的协作流程"""
        agent_info = [{"name": agent.name, "role": agent.role} for agent in agents]
        prompt = load_prompt_template("design_collaboration").format(
            task_analysis=json.dumps(task_analysis, indent=2),
            agents=json.dumps(agent_info, indent=2)
        )
        response = await self.generate(prompt)
        '''try:
            return json.loads(response)
        # except:
        #     # 默认协作流程
        #     return {
        #         "steps": [
        #             {"agent": agents[0].name, "action": "plan", "input": "task_description"},
        #             {"agent": agents[1].name, "action": "execute", "input": "previous_output"},
        #             # {"agent": agents[2].name, "action": "review", "input": "previous_output"}
        #         ],
        #         "final_output": "last_output"
        #     }
        except:
            # 默认协作流程
            agent_names = [agent.name for agent in agents]
            if len(agent_names) >= 2:
                return {
                    "steps": [
                        {"agent": agent_names[0], "action": "plan", "input": "task_description"},
                        {"agent": agent_names[1], "action": "execute", "input": "previous_output"},
                    ],
                    "final_output": "last_output"
                }
            else:
                return {
                    "steps": [
                        {"agent": agent_names[0], "action": "generate", "input": "task_description"},
                    ],
                    "final_output": "last_output"
                }'''
        parsed_json = extract_and_parse_json(response)
        if parsed_json:
            return parsed_json
        print("警告: 协作设计未能解析JSON，使用默认流程。")
        agent_names = [agent.name for agent in agents]
        if len(agent_names) >= 2:
            return {
                "steps": [
                    {"agent": agent_names[0], "action": "plan", "input": "task_description"},
                    {"agent": agent_names[1], "action": "execute", "input": "previous_output"},
                ],
                "final_output": "last_output"
            }
        elif agent_names:
            return {
                "steps": [
                    {"agent": agent_names[0], "action": "generate", "input": "task_description"},
                ],
                "final_output": "last_output"
            }
        else:
            return {"steps": [], "final_output": "none"}

    async def _evaluate_result(self,
                               result: Dict[str, Any],
                               task_description: str) -> Dict[str, Any]:
        """评估任务结果"""
        prompt = load_prompt_template("evaluate_result").format(
            task_description=task_description,
            result=json.dumps(result, indent=2)
        )
        response = await self.generate(prompt)
        # try:
        #     evaluation = json.loads(response)
        #     # 添加是否需要进化的标志
        #     evaluation["should_evolve"] = evaluation.get("score", 0) < 0.7
        #     return evaluation
        # except:
        #     return {
        #         "score": 0.5,
        #         "strengths": ["Completed the task"],
        #         "weaknesses": ["Quality could be improved"],
        #         "should_evolve": True
        #     }
        parsed_json = extract_and_parse_json(response)
        if parsed_json:
            evaluation = parsed_json
            evaluation["should_evolve"] = evaluation.get("score", 0) < 0.7
            return evaluation
        print("警告: 结果评估未能解析JSON，使用默认值。")
        return {
            "score": 0.5,
            "strengths": ["Completed the task"],
            "weaknesses": ["Quality could be improved", "Evaluation response was not valid JSON."],
            "should_evolve": True
        }

    async def _update_experience(self,
                                 task_analysis: Dict[str, Any],
                                 agents: List[Agent],
                                 result: Dict[str, Any],
                                 evaluation: Dict[str, Any]) -> None:
        """更新经验库"""
        agent_specs = []
        for agent in agents:
            agent_specs.append({
                "name": agent.name,
                "role": agent.role,
                "type": agent.type,
                "system_prompt": agent.system_prompt
            })

        experience = {
            "task_analysis": task_analysis,
            "agents_used": agent_specs,
            "result": result,
            "evaluation": evaluation
        }
        await self.experience_store.store_experience(experience)

        # 更新知识库
        if evaluation.get("score", 0) > 0.8:
            await self.knowledge_base.add_knowledge(
                task_type=task_analysis.get("task_type", "unknown"),
                knowledge=experience
            )
