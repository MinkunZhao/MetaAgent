# tests/test_evolution.py
import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock

from core.evolution_engine import EvolutionEngine
from core.agent_factory import AgentFactory

pytestmark = pytest.mark.asyncio


@pytest.fixture
@pytest.mark.asyncio
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
@pytest.mark.asyncio
def evolution_engine(mock_config):
    """初始化一个 EvolutionEngine 实例"""
    with patch('utils.api_utils.ApiManager'):
        engine = EvolutionEngine(config=mock_config)
        return engine


@pytest.fixture
def agent_factory(mock_config):
    """初始化一个 AgentFactory 实例"""
    factory = AgentFactory(config=mock_config)
    # 预加载一个模板用于测试
    factory.agent_templates['code_generator'] = {"system_prompt": "Old prompt"}
    return factory


async def test_evolve_agent_template(evolution_engine, agent_factory):
    """
    测试进化引擎是否能成功进化一个 Agent 模板
    """
    # 模拟输入数据
    task_analysis = {"task_type": "code_generator"}
    result = {"output": "Some flawed code"}
    evaluation = {"score": 0.4, "weaknesses": ["bad prompt"]}

    # 模拟 EvolutionAgent.generate 的返回值
    mock_improvement_areas = [{
        "type": "agent_template",
        "agent_type": "code_generator",
        "suggestions": ["be more specific"]
    }]

    mock_improved_template = {
        "system_prompt": "New improved prompt"
    }

    evolution_engine.evolution_agent.generate = AsyncMock(side_effect=[
        json.dumps(mock_improvement_areas),
        json.dumps(mock_improved_template)
    ])

    # 模拟 agent_factory.save_agent_template
    agent_factory.save_agent_template = AsyncMock()

    # --- 执行进化 ---
    await evolution_engine.evolve(agent_factory, task_analysis, result, evaluation)

    # --- 断言 ---
    # 1. 检查 evolution_agent.generate 是否被正确调用了两次
    assert evolution_engine.evolution_agent.generate.call_count == 2

    # 2. 检查识别改进的调用
    call_one_args = evolution_engine.evolution_agent.generate.call_args_list[0].args[0]
    assert "identify_improvements" in call_one_args

    # 3. 检查改进模板的调用
    call_two_args = evolution_engine.evolution_agent.generate.call_args_list[1].args[0]
    assert "improve_agent_template" in call_two_args
    assert "'agent_type': 'code_generator'" in call_two_args

    # 4. 检查 save_agent_template 是否被调用，并且传入了正确的模板
    agent_factory.save_agent_template.assert_called_once_with(
        'code_generator',
        mock_improved_template
    )

