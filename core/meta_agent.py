# core/meta_agent.py
import json
import re
from typing import List, Dict, Any, Optional
from agents.base_agent import Agent
from .agent_factory import AgentFactory
from .collaboration import CollaborationManager
from .evolution_engine import EvolutionEngine
from memory.experience_hub import ExperienceHub
from utils.prompt_utils import load_prompt_template


class MetaAgent(Agent):
    """
    Meta Agent负责生成和协调其他Agent来完成任务，并具有自我进化能力
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            name="MetaAgent",
            system_prompt=load_prompt_template("meta_agent_system"),
            config=config
        )
        # self.config = config
        self.agent_factory = AgentFactory(config)
        self.collaboration_manager = CollaborationManager()
        self.evolution_engine = EvolutionEngine(config, self.agent_factory)
        # self.knowledge_base = KnowledgeBase()
        # self.experience_store = ExperienceStore()
        self.experience_hub = ExperienceHub()
        # self.task_counter = 0

    async def _generate_structured_json(self, prompt: str) -> Any:
        """
        一个专用于生成纯JSON输出的内部方法，不触发自我评估。
        """
        response_text = await Agent(name="JsonGenerator", system_prompt=self.system_prompt,
                                    config=self.config).generate(prompt)
        # 简单的json提取，因为base_agent现在返回纯文本
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not match:
            match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        print(f"警告: 无法从响应中解析JSON: {response_text[:500]}")
        return None

    async def handle_task(self, task_description: str, allow_evolution: bool = False) -> Dict[str, Any]:
        # self.task_counter += 1
        is_learning_task = "### Root Cause Analysis of the Error" in task_description
        print("\n--- [MetaAgent] Analyzing Task ---")
        task_analysis = await self._analyze_task(task_description)
        print(json.dumps(task_analysis, indent=2, ensure_ascii=False))

        # 只有在非学习任务时才检索经验
        retrieved_experience = None
        if not is_learning_task:
            print("\n--- [MetaAgent] Consulting Experience Hub ---")
            retrieved_experience = self.experience_hub.retrieve_relevant_experience(task_analysis)
        if retrieved_experience:
            print("检索到成功的协作模式以指导规划。")
        else:
            print("未找到相关的过往经验，按标准流程分析。")

        print("\n--- [MetaAgent] Determining Required Agents ---")
        required_agents = await self._determine_required_agents(task_analysis, retrieved_experience)
        print(json.dumps(required_agents, indent=2, ensure_ascii=False))

        agents = await self.agent_factory.create_agents(required_agents)
        print("\n--- [MetaAgent] Created Sub-Agents ---")
        for agent in agents:
            print(f"- Name: {agent.name}, Type: {agent.type}, Role: {agent.role}")

        print("\n--- [MetaAgent] Designing Collaboration Plan ---")
        collaboration_plan = await self._design_collaboration(task_analysis, agents, retrieved_experience)
        print(json.dumps(collaboration_plan, indent=2, ensure_ascii=False))

        print("\n--- [MetaAgent] Starting Collaboration ---")
        result = await self.collaboration_manager.execute_plan(
            collaboration_plan,
            agents,
            task_description
        )

        result['context']['collaboration_plan'] = collaboration_plan

        evaluation = await self._evaluate_result(result, task_description)

        learnings = None
        if is_learning_task:
            learnings = self._extract_learnings(result.get("output", ""))
            if allow_evolution and learnings:
                print("\n--- [MetaAgent] Triggering Post-Hoc Self-Evolution from Learning ---")
                await self.evolution_engine.evolve_from_correction(
                    task_analysis,
                    learnings['root_cause'],
                    learnings['abstract_takeaways']
                )

        print("\n--- [MetaAgent] Updating Experience Hub ---")
        # 无论成功失败都更新经验，学习任务提供了宝贵的失败教训
        self.experience_hub.add_experience(task_analysis, result, evaluation, learnings)

        return result

    def _extract_learnings(self, text: str) -> Optional[Dict[str, Any]]:
        """从学习任务的输出中解析出结构化的学习成果。"""
        try:
            root_cause_match = re.search(
                r"### Root Cause Analysis of the Error\s*(.*?)\s*### Abstract Takeaways and Lessons Learned", text,
                re.DOTALL)
            takeaways_match = re.search(
                r"### Abstract Takeaways and Lessons Learned\s*(.*?)\s*### Corrected Solution Implementation", text,
                re.DOTALL)

            if root_cause_match and takeaways_match:
                return {
                    "root_cause": root_cause_match.group(1).strip(),
                    "abstract_takeaways": takeaways_match.group(1).strip().split('\n')
                }
        except Exception as e:
            print(f"解析学习内容时出错: {e}")
        return None

    async def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        if "### Root Cause Analysis" in task_description:
            # 这是一个学习任务，我们可以从中提取原始问题类型
            original_question_match = re.search(r"- \*\*Original Problem:\*\*\s*(.*?)\s*- \*\*Your Incorrect Solution",
                                                task_description, re.DOTALL)
            if original_question_match:
                task_description = original_question_match.group(1).strip()

        prompt = load_prompt_template("task_analysis").format(task_description=task_description)
        parsed_json = await self._generate_structured_json(prompt)

        if parsed_json:
            return parsed_json

        print("警告: 任务分析未能解析JSON，使用智能回退机制。")
        # desc_lower = task_description.lower()
        # math_keywords = ["math", "aime", "geometry", "algebra", "combinatorics", "number theory", "calculate",
        #                  "find the value"]
        # if any(keyword in desc_lower for keyword in math_keywords):
        #     print("  检测到数学相关关键词，回退到高复杂度数学任务类型。")
        #     return {
        #         "task_type": "high_complexity_math", "complexity": "high",
        #         "key_requirements": ["solve the math problem accurately", "provide step-by-step reasoning"],
        #         "suggested_approach": "Use specialized math agents and review the solution."
        #     }
        return {
            "task_type": "unknown", "complexity": "medium",
            "key_requirements": ["complete the task"],
            "suggested_approach": "general problem solving"
        }

    async def _determine_required_agents(self, task_analysis: Dict[str, Any], experience: Optional[Dict] = None) -> List[Dict[str, Any]]:
        # task_type = task_analysis.get("task_type", "").lower()
        # complexity = task_analysis.get("complexity", "")

        # math_related_keywords = ["math", "combinatorics", "geometry", "algebra"]
        # is_math_task = any(keyword in task_type for keyword in math_related_keywords)
        #
        # if is_math_task and complexity == "high":
        #     print("检测到高难度数学任务，使用专门的hard_math_agent和math_reviewer。")
        #     return [
        #         {
        #             "type": "hard_math_agent",
        #             "name": "HardMathSolverAgent",
        #             "role": "Execute the plan to solve the complex math problem",
        #             "custom_prompt": self.agent_factory.agent_templates.get("hard_math_agent", {}).get("system_prompt")
        #         },
        #         {
        #             "type": "math_reviewer",
        #             "name": "MathReviewerAgent",
        #             "role": "Review the mathematical solution and final answer for correctness",
        #             "custom_prompt": self.agent_factory.agent_templates.get("math_reviewer", {}).get("system_prompt")
        #         }
        #     ]

        prompt = load_prompt_template("determine_agents").format(
            task_analysis=json.dumps(task_analysis, indent=2),
            experience=json.dumps(experience, indent=2) if experience else "None"
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
                                    task_analysis: Dict,
                                    agents: List,
                                    experience: Optional[Dict] = None) -> Dict:
        agent_info = [{"name": agent.name, "role": agent.role} for agent in agents]

        '''# If there's no planner, the first agent should directly execute.
        has_planner = any(a.type == 'planner' for a in agents)
        is_math_task = "math" in task_analysis.get("task_type", "")

        # For high-complexity math, a direct execution is better than a generic plan.
        if not has_planner or is_math_task:
            executor = next((a.name for a in agents if a.type in ['hard_math_agent', 'executor']), agents[0].name)
            return {"steps": [{"agent": executor, "action": "execute", "input": "task_description"}],
                    "final_output": "last_output"}'''

        prompt = load_prompt_template("design_collaboration").format(
            task_analysis=json.dumps(task_analysis, indent=2),
            agents=json.dumps(agent_info, indent=2),
            experience=json.dumps(experience, indent=2) if experience else "None"
        )

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
        # 简化评估，因为核心学习现在由答案对比驱动
        # 我们可以假设，如果触发了学习任务，那么之前的尝试就是失败的
        if "### Root Cause Analysis" in task_description:
            return {"score": 0.2, "weaknesses": ["Previous attempt was incorrect, triggering a learning cycle."],
                    "should_evolve": True}
        else:
            # 在这个新流程中，我们无法仅通过输出来判断对错，这个判断移到了aime.py中
            # 所以这里的评估只做基本检查
            if result.get("output") and "error" not in result["output"].lower():
                return {"score": 0.9, "strengths": ["Completed without system errors."], "should_evolve": False}
            else:
                return {"score": 0.1, "weaknesses": ["Task execution resulted in an error or no output."],
                        "should_evolve": True}

    # async def _update_experience(self,
    #                              task_analysis: Dict[str, Any],
    #                              agents: List[Agent],
    #                              result: Dict[str, Any],
    #                              evaluation: Dict[str, Any]) -> None:
    #     """更新经验库"""
    #     agent_specs = [{"name": a.name, "type": a.type, "system_prompt": a.system_prompt} for a in agents]
    #     experience = {
    #         "task_analysis": task_analysis,
    #         "agents_used": agent_specs,
    #         "result_trajectory": result,
    #         "evaluation": evaluation
    #     }
    #     await self.experience_store.store_experience(experience)