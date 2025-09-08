# core/agent_factory.py
from typing import List, Dict, Any
import os
# from mcp_agent.agents.agent import Agent
from utils.prompt_utils import load_prompt_template
import json
from agents.base_agent import Agent
from agents.specialized.code_agent import CodeAgent
from agents.specialized.review_agent import ReviewAgent
from agents.specialized.test_agent import TestAgent
from utils.json_utils import extract_and_parse_json
from agents.specialized.math_agent import MathAgent


class AgentFactory:
    """
    Agent工厂，负责创建不同类型的Agent
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化Agent工厂"""
        self.config = config
        self.agent_templates = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """加载Agent模板"""
        templates_path = os.path.join("config", "agent_templates.json")
        if os.path.exists(templates_path):
            with open(templates_path, "r", encoding="utf-8") as f:
                self.agent_templates = json.load(f)
        else:
            # 默认模板
            self.agent_templates = {
                "planner": {
                    "system_prompt": "You are a Planning Agent responsible for breaking down complex tasks into manageable steps."
                },
                "executor": {
                    "system_prompt": "You are an Execution Agent responsible for implementing solutions based on plans."
                },
                "reviewer": {
                    "system_prompt": "You are a Review Agent responsible for critically analyzing solutions for correctness and quality."
                },
                "code_generator": {
                    "system_prompt": "You are a Code Generation Agent specialized in writing clean, efficient, and correct code."
                },
                # "code_reviewer": {
                #     "system_prompt": "You are a Code Review Agent specialized in identifying bugs, inefficiencies, and style issues in code."
                # },
                "test_writer": {
                    "system_prompt": "You are a Test Writing Agent specialized in creating comprehensive test cases for code."
                }
            }

    async def create_agents(self, agent_specs: List[Dict[str, Any]]) -> List[Agent]:
        """
        根据规格创建一组Agent
        """
        agents = []
        if not isinstance(agent_specs, list):
            print(f"警告: 'agent_specs' 不是列表，无法创建代理。接收到的类型: {type(agent_specs)}")
            return agents

        for spec in agent_specs:
            agent_type = spec.get("type", "generic")
            template = self.agent_templates.get(agent_type, {
                "system_prompt": "You are a helpful assistant agent."
            })
            system_prompt = spec.get("custom_prompt", template["system_prompt"])

            # 根据type实例化专门化Agent
            if agent_type in ["code_generator", "code_agent", "executor"]:
                agent = CodeAgent(
                    name=spec.get("name", f"{agent_type.capitalize()}Agent"),
                    system_prompt=system_prompt,
                    config=self.config
                )
            # MODIFIED: Route new math_reviewer here
            elif agent_type in ["reviewer", "code_reviewer", "math_reviewer"]:
                agent = ReviewAgent(
                    name=spec.get("name", f"{agent_type.capitalize()}Agent"),
                    system_prompt=system_prompt,
                    config=self.config
                )
            elif agent_type in ["test_writer", "test_agent"]:
                agent = TestAgent(
                    name=spec.get("name", f"{agent_type.capitalize()}Agent"),
                    system_prompt=system_prompt,
                    config=self.config
                )
            # MODIFIED: Add hard_math_agent specialization
            elif agent_type == "hard_math_agent":
                agent = MathAgent(
                    name=spec.get("name", "HardMathAgent"),
                    system_prompt=system_prompt,
                    config=self.config
                )
            else:
                agent = Agent(
                    name=spec.get("name", f"{agent_type.capitalize()}Agent"),
                    system_prompt=system_prompt,
                    config=self.config
                )

            agent.role = spec.get("role", f"Act as a {agent_type}")
            agent.type = agent_type
            agents.append(agent)

        return agents

    async def generate_agent_spec(self, task_description: str, agent_type: str) -> Dict[str, Any]:
        """
        生成特定任务的Agent规格
        这是自我进化机制的一部分，可以为特定任务创建自定义Agent
        """
        # 创建一个临时Agent来生成规格
        spec_generator = Agent(
            name="SpecGenerator",
            system_prompt="You are an expert at designing specialized AI agents for specific tasks.",
            config = self.config
        )

        prompt = load_prompt_template("generate_agent_spec").format(
            task_description=task_description,
            agent_type=agent_type,
        )

        response = await spec_generator.generate(prompt)

        # try:
        #     agent_spec = json.loads(response)
        #     return agent_spec
        # except:
        #     # 如果不是有效的JSON，返回默认规格
        #     return {
        #         "type": agent_type,
        #         "name": f"Custom{agent_type.capitalize()}Agent",
        #         "role": f"Specialized {agent_type} for the current task",
        #         "custom_prompt": f"You are a specialized {agent_type} agent created specifically for handling tasks related to: {task_description}"
        #     }
        agent_spec = extract_and_parse_json(response)

        if agent_spec:
            return agent_spec
        print(f"警告: 为 '{agent_type}' 生成代理规格时未能解析JSON，使用默认值。")
        return {
            "type": agent_type,
            "name": f"Custom{agent_type.capitalize()}Agent",
            "role": f"Specialized {agent_type} for the current task",
            "custom_prompt": f"You are a specialized {agent_type} agent created specifically for handling tasks related to: {task_description}"
        }

    async def save_agent_template(self, agent_type: str, template: Dict[str, Any]) -> None:
        """保存新的Agent模板"""
        self.agent_templates[agent_type] = template

        # 保存到文件
        templates_path = os.path.join("config", "agent_templates.json")
        os.makedirs(os.path.dirname(templates_path), exist_ok=True)

        with open(templates_path, "w", encoding="utf-8") as f:
            json.dump(self.agent_templates, f, indent=2)
