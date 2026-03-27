import os
import logging
import networkx as nx
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class HanaKnowledgeGraph:
    def __init__(self, persist_path: str = "data/memory/knowledge_graph.gml"):
        self.persist_path = os.path.abspath(persist_path)
        
        # Garante o diretório
        dir_path = os.path.dirname(self.persist_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        logger.info(f"[KNOWLEDGE GRAPH] Inicializando Grafo em: {self.persist_path}")
        
        # Inicializa ou carrega o grafo
        if os.path.exists(self.persist_path):
            try:
                self.graph = nx.read_gml(self.persist_path)
                logger.info("[KNOWLEDGE GRAPH] Grafo carregado com sucesso.")
            except Exception as e:
                logger.error(f"[KNOWLEDGE GRAPH] Erro ao carregar grafo: {e}. Criando novo.")
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

    def add_fact(self, subject: str, relation: str, object_val: str):
        """Adiciona um fato ao grafo."""
        # Normalização básica
        s = subject.strip().lower()
        r = relation.strip().lower()
        o = object_val.strip().lower()
        
        # Adiciona nós se não existirem
        if not self.graph.has_node(s):
            self.graph.add_node(s, type="entity")
        if not self.graph.has_node(o):
            self.graph.add_node(o, type="entity")
            
        # Adiciona/Atualiza a aresta com a relação
        self.graph.add_edge(s, o, relation=r)
        
        # Salva o grafo
        self.save()
        logger.info(f"[KNOWLEDGE GRAPH] Fato adicionado: {s} --[{r}]--> {o}")

    def get_related_facts(self, entity: str) -> List[Tuple[str, str, str]]:
        """Retorna todos os fatos (Triplas) relacionados a uma entidade."""
        e = entity.strip().lower()
        if not self.graph.has_node(e):
            return []
            
        facts = []
        
        # Fatos onde a entidade é o sujeito
        for target in self.graph.successors(e):
            rel = self.graph.get_edge_data(e, target).get("relation", "relacionado_a")
            facts.append((e, rel, target))
            
        # Fatos onde a entidade é o objeto
        for source in self.graph.predecessors(e):
            rel = self.graph.get_edge_data(source, e).get("relation", "relacionado_a")
            facts.append((source, rel, e))
            
        return facts

    def save(self):
        """Salva o grafo em disco."""
        try:
            nx.write_gml(self.graph, self.persist_path)
        except Exception as e:
            logger.error(f"[KNOWLEDGE GRAPH] Erro ao salvar grafo: {e}")

    def get_graph_context_string(self, entities: List[str]) -> str:
        """Retorna uma string formatada com os fatos encontrados para uma lista de entidades."""
        all_relevant_facts = []
        for ent in entities:
            all_relevant_facts.extend(self.get_related_facts(ent))
            
        if not all_relevant_facts:
            return ""
            
        # Remove duplicatas e formata
        unique_facts = list(set(all_relevant_facts))
        formatted = "\n".join([f"- {s} [{r}] {o}" for s, r, o in unique_facts])
        return f"\n=== FATOS DO CONHECIMENTO (LONG-TERM) ===\n{formatted}\n"
