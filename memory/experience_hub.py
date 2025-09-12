import networkx as nx
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


class ExperienceHub:
    """
    记忆模块，以图的形式存储和检索经验。
    这有助于MetaAgent从过去的任务中学习，以提高未来的表现。
    """
    def __init__(self, db_path="memory/experience_graph.json"):
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self._load_graph()

    def _load_graph(self):
        """从文件加载经验图。"""
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                self.graph = nx.node_link_graph(data)
        else:
            print("未找到经验图，将创建一个新的。")

    def _save_graph(self):
        """将经验图保存到文件。"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_experience(self, task_analysis: Dict[str, Any], result: Dict[str, Any], evaluation: Dict[str, Any]):
        """
        处理一个已完成的任务，并将学到的知识存储在图中。
        它会抽象出成功的模式，而不仅仅是记录步骤。
        """
        if evaluation.get("score", 0) < 0.8:
            # 目前，我们只从成功的任务中学习，以确保知识的质量。
            return

        # 1. 创建/更新问题类型节点
        problem_type_id = f"problem_{task_analysis.get('task_type', 'generic')}"
        self.graph.add_node(problem_type_id, type='problem_type',
                            access_count=self.graph.nodes.get(problem_type_id, {}).get('access_count', 0) + 1)

        # 2. 创建/更新概念节点
        for concept in task_analysis.get('knowledge_domains', []):
            concept_id = f"concept_{concept.lower().replace(' ', '_')}"
            self.graph.add_node(concept_id, type='concept', label=concept)
            self.graph.add_edge(problem_type_id, concept_id, type='USES_CONCEPT')

        # 3. 抽象并存储成功的协作模式
        try:
            plan = result['context']['collaboration_plan']
            pattern_id = f"pattern_{hash(json.dumps(plan, sort_keys=True))}"

            if not self.graph.has_node(pattern_id):
                self.graph.add_node(pattern_id, type='pattern', plan=plan, success_count=1,
                                    last_used=datetime.utcnow().isoformat())
            else:
                self.graph.nodes[pattern_id]['success_count'] += 1
                self.graph.nodes[pattern_id]['last_used'] = datetime.utcnow().isoformat()

            self.graph.add_edge(problem_type_id, pattern_id, type='SOLVED_BY')
        except KeyError:
            print("警告: 在结果上下文中找不到协作计划，无法抽象模式。")

        self._save_graph()
        print(f"  [记忆模块] 已为任务类型 '{problem_type_id}' 添加成功经验。")

    def retrieve_relevant_experience(self, task_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        为一个新任务检索最相关的历史经验。
        它优先考虑成功的协作模式。
        """
        problem_type_id = f"problem_{task_analysis.get('task_type', 'generic')}"
        if not self.graph.has_node(problem_type_id):
            return None

        candidate_patterns = []
        for successor in self.graph.successors(problem_type_id):
            if self.graph.nodes[successor].get('type') == 'pattern':
                pattern_node = self.graph.nodes[successor]
                candidate_patterns.append({
                    'plan': pattern_node.get('plan'),
                    'success_count': pattern_node.get('success_count', 1)
                })

        if not candidate_patterns:
            return None

        best_pattern = max(candidate_patterns, key=lambda p: p['success_count'])

        print(f"  [记忆模块] 检索到相关经验：发现一个有 {best_pattern['success_count']} 次成功记录的模式。")

        return {
            "suggested_plan": best_pattern['plan']
        }
