import asyncio
import json
import os
from typing import Dict, Any
import argparse

from core.meta_agent import MetaAgent
from utils.api_utils import ApiManager
from evaluation.human_eval import HumanEvalRunner
from evaluation.gsm8k import Gsm8kRunner
from evaluation.hardmath import HardMathRunner


async def main():
    """主入口函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Evolving Multi-Agent System")
    parser.add_argument("--config", type=str, default="config/system_config.json", help="Path to configuration file")
    parser.add_argument("--task", type=str, help="Task to execute")
    parser.add_argument("--eval-humaneval", action="store_true", help="Run evaluation on HumanEval dataset")
    # 新增GSM8K评估参数
    parser.add_argument("--eval-gsm8k", action="store_true", help="Run evaluation on GSM8K dataset")
    parser.add_argument("--eval-hardmath", default=1, action="store_true", help="Run evaluation on HARDMath dataset with evolution and testing phases")
    parser.add_argument("--output", type=str, default="results", help="Output directory for results")
    # parser.add_argument("--eval", dest='eval_humaneval', action="store_true", help="DEPRECATED: Use --eval-humaneval")
    args = parser.parse_args()

    # 加载配置
    if os.path.exists(args.config):
        with open(args.config, "r") as f:
            config = json.load(f)
    else:
        # config = {
        #     "openai_api_key": "",
        #     "default_model": "gpt-4.1-mini",
        #     "log_level": "info",
        #     "max_tokens_per_request": 256,
        #     "temperature": 0.5
        # }

        config = {
            "yibu_api_key": "",
            "yibu_base_url": "https://yibuapi.com",
            "default_model": "claude-3-7-sonnet-latest",
            "timeout": 60,
            "max_tokens": 1024,
            "temperature": 0.5
        }

        os.makedirs(os.path.dirname(args.config), exist_ok=True)
        with open(args.config, "w") as f:
            json.dump(config, f, indent=2)

    # api_manager = ApiManager(config)

    # 创建Meta Agent
    meta_agent = MetaAgent(config)

    # 确保输出目录存在
    os.makedirs(args.output, exist_ok=True)

    if args.eval_humaneval:
        # 运行HumanEval评估
        print("Running HumanEval evaluation...")
        runner = HumanEvalRunner(meta_agent, config)
        results = await runner.run_evaluation()

        # 保存结果
        output_path = os.path.join(args.output, "human_eval_results.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Evaluation results saved to {output_path}")
        print(f"Pass@1: {results['pass@1']:.2f}")

    elif args.eval_gsm8k:
        # 运行GSM8K评估
        print("Running GSM8K evaluation...")
        runner = Gsm8kRunner(meta_agent, config)
        results = await runner.run_evaluation()

        # 保存结果
        output_path = os.path.join(args.output, "gsm8k_results.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Evaluation results saved to {output_path}")
        print(f"Accuracy: {results['accuracy']:.2f}")

    elif args.eval_hardmath:
        # 运行 HARDMath 评估
        print("Running HARDMath evaluation...")
        runner = HardMathRunner(meta_agent, config)

        # 1. 进化阶段
        # 使用前5个训练问题进行进化 (可根据需要调整数量)
        await runner.run_evolution_phase(num_problems=5)

        # 2. 测试阶段
        results = await runner.run_testing_phase()

        # 保存结果
        if results:
            output_path = os.path.join(args.output, "hardmath_results.json")
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)

            print(f"HARDMath evaluation results saved to {output_path}")
            print(f"Accuracy: {results.get('accuracy', 0):.2f}")
        else:
            print("HARDMath evaluation did not produce any results.")

    elif args.task:
        # 执行单个任务
        print(f"Executing task: {args.task}")
        result = await meta_agent.handle_task(args.task)

        # 保存结果
        output_path = os.path.join(args.output, "task_result.json")
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"Task result saved to {output_path}")
        print("\nFinal output:")
        print(result["output"])

    else:
        # 交互模式
        print("Evolving Multi-Agent System")
        print("Enter your task, or type 'exit' to quit.")

        while True:
            task = input("\nTask: ")
            if task.lower() == "exit":
                break

            result = await meta_agent.handle_task(task)
            print("\nOutput:")
            print(result["output"])


if __name__ == "__main__":
    asyncio.run(main())
