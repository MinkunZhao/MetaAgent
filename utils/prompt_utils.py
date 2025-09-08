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
    template = _DEFAULT_TEMPLATES.get(template_name, f"Template '{template_name}' not found.")
    _PROMPT_CACHE[template_name] = template
    return template

# 默认模板 (已更新以支持新的进化机制)
_DEFAULT_TEMPLATES = {
    "meta_agent_system": """You are MetaAgent, a sophisticated AI coordinator that can generate and manage specialized AI agents to solve complex tasks. Your responsibilities include:
1. Analyzing user tasks to determine the most effective approach.
2. Creating specialized agents with tailored prompts for specific sub-tasks.
3. Coordinating collaboration between multiple agents. Your system dynamically triggers refinement loops based on agent confidence, ensuring quality.
4. Evaluating results and improving the system through self-evolution based on performance, agent confidence scores, and refinement trajectories.
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

For 'high' complexity tasks, you MUST include a 'reviewer' agent to enable self-correction loops. For simpler tasks, a 'planner' and 'executor' is often sufficient.

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

Create a step-by-step collaboration plan. Your plan should be logical, starting with planning and moving to execution. You DO NOT need to add a 'review' step, as the system will trigger it automatically if an agent's confidence is low.

CRITICAL: Return your response as a single, valid JSON object.
The JSON object must have these keys:
- steps: An array of steps, each with:
  - agent: The name of the agent responsible.
  - action: What the agent should do (e.g., "plan", "execute", "code").
  - input: Where the input comes from (e.g., "task_description", "previous_output").
- final_output: Which step's output is the final result (usually "last_output").
""",

    "evaluate_result": """Evaluate the quality of the following result for the given task.

TASK: {task_description}
RESULT: {result}

Provide a comprehensive evaluation.

CRITICAL: Return your evaluation as a single, valid JSON object.
The JSON object must have these keys:
- score: A numeric rating from 0.0 (failure) to 1.0 (perfect).
- strengths: An array of identified strengths.
- weaknesses: An array of identified weaknesses.
- improvement_suggestions: Specific suggestions for what could have been done better.
""",

    "identify_improvements": """Analyze the following task execution trajectory and identify areas for system improvement. The goal is to propose a single, high-impact change to an agent's core instructions (system prompt) to prevent similar failures or low-confidence outputs in the future.

TASK ANALYSIS: {task_analysis}
EXECUTION TRAJECTORY: {result_trajectory}
FINAL EVALUATION: {evaluation}

Focus on the steps with low confidence or where refinement was needed. What was the root cause of the agent's uncertainty or error? Based on this, suggest a specific improvement.

CRITICAL: Return a valid JSON array containing a SINGLE improvement object.
The object must have these keys:
- type: Must be "agent_template".
- specific_element_to_improve": The type of the agent that needs improvement (e.g., "hard_math_agent", "executor").
- suggestions: An array of specific, actionable suggestions to add to the agent's system prompt to address the root cause. (e.g., "Add a directive to always double-check calculations before finalizing the answer.").
""",

    "improve_agent_template": """Improve the following agent template based on analysis of its performance.

AGENT TYPE: {agent_type}
CURRENT TEMPLATE: {current_template}
PERFORMANCE CONTEXT: {context_info}
IMPROVEMENT SUGGESTIONS: {suggestions}

Your task is to rewrite the `system_prompt` for this agent. The new prompt must be a strict improvement. It should integrate the `suggestions` and address the failures or uncertainties described in the `context_info`. Make the agent's instructions more robust, precise, and better equipped to handle similar tasks in the future.

CRITICAL: Return a single, valid JSON object representing the improved agent template, containing only the "system_prompt" key and its new, complete string value.
""",

    "synthesize_experiences": """You are a meta-analyst for an AI agent system. Analyze the following recent experiences (each including task type, agent trajectory with confidence scores, and final evaluation) to identify a systemic, recurring weakness.

RECENT EXPERIENCES:
{experiences_json}

Your goal is to find a pattern. For instance, does the 'hard_math_agent' consistently express low confidence on algebra problems? Does the 'executor' agent often fail to follow complex plans? Based on the most critical recurring pattern, propose a single, high-impact evolution for the responsible agent's template.

CRITICAL: Return a valid JSON array containing a SINGLE improvement plan object.
The object must have these keys:
- type: Must be "agent_template".
- specific_element_to_improve": The agent type that needs the most critical update (e.g., "hard_math_agent").
- reasoning": A brief explanation of the systemic weakness you identified from the data.
- suggestions": An array of concrete suggestions for improving its system prompt to fix this systemic issue.
"""
}