# evolving_multi_agent/memory/experience_hub.py
import networkx as nx
import json
import os
from typing import Dict, Any, List, Optional


class ExperienceHub:
    def __init__(self, db_path="memory/experience_graph.json"):
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self._load_graph()

    def _load_graph(self):
        """从文件加载经验图。"""
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.graph = nx.node_link_graph(data)
        else:
            print("未找到经验图，将创建一个新的。")

    def _save_graph(self):
        """将经验图保存到文件。"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_experience(self, task_analysis: Dict, result: Dict, evaluation: Dict, learnings: Optional[Dict] = None):
        """存储经验，优先存储从学习中提取的抽象启发式策略。"""
        problem_type = task_analysis.get('task_type', 'generic')
        concepts = task_analysis.get('knowledge_domains', [])

        # 存储从失败中学习到的抽象教训
        if learnings and learnings.get('abstract_takeaways'):
            for takeaway in learnings['abstract_takeaways']:
                if not takeaway.strip(): continue
                heuristic_id = f"heuristic_{hash(takeaway)}"
                if not self.graph.has_node(heuristic_id):
                    self.graph.add_node(heuristic_id, type='heuristic', text=takeaway, positive_count=0,
                                        negative_count=1)
                else:
                    self.graph.nodes[heuristic_id]['negative_count'] += 1

                # 将启发式策略关联到问题类型和概念
                self.graph.add_edge(f"problem_{problem_type}", heuristic_id)
                for concept in concepts:
                    self.graph.add_edge(f"concept_{concept}", heuristic_id)
            print(f"  [记忆模块] 从失败中学习并存储了 {len(learnings['abstract_takeaways'])} 条启发式教训。")

        # 如果任务成功，将成功的计划与相关启发式策略关联起来
        elif evaluation.get('score', 0) >= 0.8:
            plan = result.get('context', {}).get('collaboration_plan')
            if plan:
                pattern_id = f"pattern_{hash(json.dumps(plan, sort_keys=True))}"
                self.graph.add_node(pattern_id, type='successful_pattern', plan=plan)
                self.graph.add_edge(f"problem_{problem_type}", pattern_id)
                # 将这个成功模式与该问题类型已知的所有启发式策略关联
                # 表示这个模式符合这些好的实践
                for heuristic_id in self.retrieve_relevant_heuristics(task_analysis):
                    self.graph.add_edge(heuristic_id, pattern_id)
                    self.graph.nodes[heuristic_id]['positive_count'] += 1
            print(f"  [记忆模块] 存储了1条成功的协作模式。")

        self._save_graph()

    def retrieve_relevant_heuristics(self, task_analysis: Dict) -> List[str]:
        """根据任务类型和概念，检索最相关的启发式策略文本。"""
        problem_type = task_analysis.get('task_type', 'generic')
        concepts = task_analysis.get('knowledge_domains', [])

        relevant_heuristic_ids = set()

        # 从问题类型查找
        source_nodes = [f"problem_{problem_type}"] + [f"concept_{c}" for c in concepts]

        for node in source_nodes:
            if self.graph.has_node(node):
                for successor in self.graph.successors(node):
                    if self.graph.nodes[successor].get('type') == 'heuristic':
                        relevant_heuristic_ids.add(successor)

        # 排序：优先选择正面案例多、负面案例少的启发式策略
        sorted_heuristics = sorted(
            list(relevant_heuristic_ids),
            key=lambda hid: self.graph.nodes[hid].get('positive_count', 0) - self.graph.nodes[hid].get('negative_count',
                                                                                                       0),
            reverse=True
        )

        return [self.graph.nodes[hid]['text'] for hid in sorted_heuristics]

    def retrieve_relevant_experience(self, task_analysis: Dict) -> Dict:
        """检索相关的启发式策略和成功的协作模式。"""
        heuristics = self.retrieve_relevant_heuristics(task_analysis)

        # (可选) 未来可加入检索与这些启发式策略相关的成功模式

        if heuristics:
            print(f"  [记忆模块] 检索到 {len(heuristics)} 条相关的解题原则/启发式策略。")

        return {
            "retrieved_heuristics": heuristics,
            "successful_patterns": []  # 简化：目前主要依赖启发式策略
        }