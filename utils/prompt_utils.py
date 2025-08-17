# utils/prompt_utils.py
import os
from typing import Dict, Any

_PROMPT_CACHE = {}


def load_prompt_template(template_name: str) -> str:
    """
    加载提示模板
    """
    if template_name in _PROMPT_CACHE:
        return _PROMPT_CACHE[template_name]

    # 简单的模板加载逻辑
    template = _DEFAULT_TEMPLATES.get(template_name, f"Template '{template_name}' not found.")
    _PROMPT_CACHE[template_name] = template
    return template


# 默认模板
_DEFAULT_TEMPLATES = {
    "meta_agent_system": """You are MetaAgent, a sophisticated AI coordinator that can generate and manage specialized AI agents to solve complex tasks. Your responsibilities include:
1. Analyzing user tasks to determine the most effective approach.
2. Creating specialized agents with tailored prompts for specific sub-tasks.
3. Coordinating collaboration between multiple agents, including iterative refinement loops, to solve problems.
4. Evaluating results and improving the system through self-evolution based on both single-task performance and long-term experience synthesis.
Your goal is to harness the collective intelligence of multiple specialized agents to achieve superior results.
""",

    "task_analysis": """Analyze the following task carefully and provide a structured assessment.

TASK: {task_description}

CRITICAL: Your response must be a single, valid JSON object. Do not add any text before or after the JSON.
Provide your analysis in JSON format with the following fields:
- task_type: The primary category (e.g., "code_generation", "high_complexity_math", "text_analysis").
- complexity: A rating of task complexity ("low", "medium", "high").
- key_requirements: A list of the most important requirements.
- subtasks: A breakdown of the task into logical subtasks.
- knowledge_domains: List of relevant knowledge domains.
- potential_challenges: Anticipated difficulties.
- suggested_approach: A high-level strategy.
""",

    "determine_agents": """Based on the following task analysis, determine the ideal set of specialized agents needed.

TASK ANALYSIS: {task_analysis}

For each required agent, specify its type, role, and a tailored system prompt.
IMPORTANT: For 'high' complexity tasks, always include a 'reviewer' agent to enable a refinement loop. For simpler tasks, a 'planner' and 'executor' is often sufficient.

CRITICAL: Return your response as a valid JSON array of agent specifications. The response must start with `[` and end with `]`.
Each object must have these keys:
- type: The agent's category (e.g., "planner", "executor", "hard_math_agent", "reviewer").
- name: A descriptive name (e.g., "MathProofExecutor").
- role: A concise description of this agent's role.
- custom_prompt: A tailored system prompt for this agent.
""",

    "design_collaboration": """Design a collaboration workflow for the following agents to solve a task.

TASK ANALYSIS: {task_analysis}
AVAILABLE AGENTS: {agents}

Create a step-by-step collaboration plan. If a 'reviewer' agent is present, you MUST include a 'review_and_refine' action step after the main execution step. This enables a self-correction loop.

CRITICAL: Return your response as a single, valid JSON object.
The JSON object must have these keys:
- steps: An array of steps, each with:
  - agent: The name of the agent responsible.
  - action: What the agent should do (e.g., "plan", "execute", "review_and_refine").
  - input: Where the input comes from (e.g., "task_description", "previous_output").
- final_output: Which step's output is the final result (usually "last_output").
""",

    "evaluate_result": """Evaluate the quality of the following result for the given task.

TASK: {task_description}
RESULT: {result}

Provide a comprehensive evaluation.

CRITICAL: Return your evaluation as a single, valid JSON object.
The JSON object must have these keys:
- score: A numeric rating from 0.0 to 1.0.
- strengths: An array of identified strengths.
- weaknesses: An array of identified weaknesses.
- improvement_suggestions: Specific suggestions for improvement.
""",

    "identify_improvements": """Analyze the following task execution and identify areas for system improvement.

TASK ANALYSIS: {task_analysis}
EXECUTION RESULT: {result}
EVALUATION: {evaluation}

Based on the weaknesses and evaluation score, suggest ONE specific, high-impact improvement.

CRITICAL: Return a valid JSON array containing a SINGLE improvement object.
The object must have these keys:
- type: The type of improvement (e.g., "agent_template").
- specific_element_to_improve": The name of the item to improve (e.g., agent type like "hard_math_agent" or "code_generator").
- suggestions: An array of specific improvement suggestions for the element's system prompt.
""",

    "improve_agent_template": """Improve the following agent template based on analysis of its performance.

AGENT TYPE: {agent_type}
CURRENT TEMPLATE: {current_template}
CONTEXT: {context_info}
IMPROVEMENT SUGGESTIONS: {suggestions}

Create an improved template that addresses the identified issues. Incorporate the suggestions into the new system prompt to make it more robust, knowledgeable, and effective.

CRITICAL: Return a single, valid JSON object representing the improved agent template, containing only the "system_prompt" key and its new value.
""",

    "synthesize_experiences": """You are a meta-analyst for an AI agent system. Analyze the following recent experiences (task analysis, agents used, and evaluation scores) to identify overarching patterns and suggest a single, high-impact evolution for an agent template.

RECENT EXPERIENCES:
{experiences_json}

Your goal is to move beyond single-task failures and find systemic weaknesses. For example, if multiple math tasks fail due to calculation errors, suggest improving the 'hard_math_agent' prompt to emphasize double-checking work.

CRITICAL: Return a valid JSON array containing a SINGLE improvement plan object.
The object must have these keys:
- type: Must be "agent_template".
- specific_element_to_improve": The agent type that needs the most critical update (e.g., "hard_math_agent", "code_generator").
- reasoning": A brief explanation of why this agent needs evolution based on the data.
- suggestions": An array of concrete suggestions for improving its system prompt.
"""
}