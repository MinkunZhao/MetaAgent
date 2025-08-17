# tests/test_meta_agent.py
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from core.meta_agent import MetaAgent

# 使用 pytest.mark.asyncio 来标记异步测试函数
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_config():
    """提供一个模拟的配置字典"""
    return {
        "openai_api_key": "",
        "default_model": "gpt-4.1-mini",
        "log_level": "info",
        "max_tokens_per_request": 256,
        "temperature": 0.5
    }


@pytest.fixture
def meta_agent(mock_config):
    # 初始化一个 MetaAgent 实例以进行测试
    with patch('utils.api_utils.ApiManager'):
        agent = MetaAgent(config=mock_config)
        return agent


async def test_meta_agent_initialization(meta_agent):
    # 测试 MetaAgent 是否被正确初始化
    assert meta_agent.name == "MetaAgent"
    assert meta_agent.agent_factory is not None
    assert meta_agent.collaboration_manager is not None
    assert meta_agent.evolution_engine is not None


async def test_handle_task_full_flow(meta_agent, mock_config):
    """
    测试 handle_task 方法的完整端到端流程（使用模拟）
    """
    task_description = "Create a python function to add two numbers."

    # 模拟 MetaAgent.generate 的一系列返回值
    mock_task_analysis = {
        "task_type": "code_generation",
        "complexity": "low",
        "key_requirements": ["function that adds two numbers"],
        "subtasks": ["define function", "return sum"],
        "knowledge_domains": ["python"],
        "potential_challenges": [],
        "suggested_approach": "simple function"
    }
    mock_required_agents = [
        {"type": "executor", "name": "CodeExecutor", "role": "Write the code", "custom_prompt": "..."}
    ]
    mock_collab_plan = {
        "steps": [{"agent": "CodeExecutor", "action": "code", "input": "task_description"}],
        "final_output": "last_output"
    }
    mock_evaluation = {
        "score": 0.9,
        "strengths": ["Correct and simple"],
        "weaknesses": [],
        "should_evolve": False
    }

    # 使用 AsyncMock 来模拟异步方法 generate
    meta_agent.generate = AsyncMock(side_effect=[
        json.dumps(mock_task_analysis),
        json.dumps(mock_required_agents),
        json.dumps(mock_collab_plan),
        json.dumps(mock_evaluation)
    ])

    # 模拟子 Agent 的 generate 方法
    # 我们将 patch Agent 基类中的 generate 方法
    mock_executor_output = "def add(a, b): return a + b"
    with patch('agents.base_agent.Agent.generate', new_callable=AsyncMock,
               return_value=mock_executor_output) as mock_sub_agent_generate:
        # 运行 handle_task
        result = await meta_agent.handle_task(task_description)

        # --- 断言 ---
        # 1. 检查 MetaAgent.generate 是否被按预期调用
        assert meta_agent.generate.call_count == 4

        # 2. 检查子 agent 是否被正确调用
        # AgentFactory 会创建一个 Agent 实例，然后 CollaborationManager 会调用它的 generate 方法
        mock_sub_agent_generate.assert_called_once()

        # 3. 检查最终输出是否正确
        assert result['output'] == mock_executor_output
        assert result['steps'][0]['agent'] == "CodeExecutor"
        assert result['steps'][0]['output'] == mock_executor_output

        # 4. 检查是否没有触发进化
        assert "Triggering Self-Evolution" not in result.get("log", "")

