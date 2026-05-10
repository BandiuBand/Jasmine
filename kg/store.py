import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from .embeddings import cosine_similarity, get_embedding

DEDUP_THRESHOLD = 0.90

_RELATION = {
    "fact": "has_fact",
    "intent": "intends",
    "emotion": "expressed_emotion",
    "behavior": "shows_behavior",
}


class KnowledgeGraph:
    def __init__(self, graph_path: str, embed_url: str, embed_model: str):
        self.graph_path = graph_path
        self.embed_url = embed_url
        self.embed_model = embed_model
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self.graph_path):
            with open(self.graph_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        self.nodes: Dict[str, Dict] = data.get("nodes", {})
        self.edges: List[Dict] = data.get("edges", [])
        self.processed: set = set(data.get("processed", []))

    def save(self):
        os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "nodes": self.nodes,
                    "edges": self.edges,
                    "processed": list(self.processed),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _short_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def _get_or_create_person(self, identifier: str, chat_id: str) -> str:
        for nid, node in self.nodes.items():
            if node["type"] == "person" and node["value"] == identifier:
                return nid
        nid = self._short_id()
        self.nodes[nid] = {
            "id": nid,
            "type": "person",
            "value": identifier,
            "chat_id": chat_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "mentions": 0,
        }
        return nid

    def _find_duplicate(self, embedding: List[float], node_type: str) -> Optional[str]:
        for nid, node in self.nodes.items():
            if node["type"] != node_type:
                continue
            stored = node.get("embedding")
            if not stored:
                continue
            if cosine_similarity(embedding, stored) >= DEDUP_THRESHOLD:
                return nid
        return None

    def _normalize_value(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.lower()).strip()
        return re.sub(r"[^\w\sа-яіїєґ'-]", "", normalized)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_processed(self, key: str) -> bool:
        return key in self.processed

    def mark_processed(self, key: str):
        self.processed.add(key)

    def add_items(
        self,
        items: List[Dict[str, Any]],
        sender: str,
        chat_identifier: str,
        chat_id: str,
        source_ref: str,
    ) -> int:
        person_id = self._get_or_create_person(sender, chat_id)
        self.nodes[person_id]["mentions"] = self.nodes[person_id].get("mentions", 0) + 1
        self.nodes[person_id]["updated_at"] = self._now()

        added = 0
        for item in items:
            itype = item["type"]
            value = item["value"]
            confidence = float(item.get("confidence", 0.8))
            value_norm = self._normalize_value(value)

            existing_id = None
            for nid, node in self.nodes.items():
                if node.get("type") != itype:
                    continue
                if self._normalize_value(node.get("value", "")) == value_norm and value_norm:
                    existing_id = nid
                    break

            emb = get_embedding(value, self.embed_url, self.embed_model)
            if not existing_id:
                existing_id = self._find_duplicate(emb, itype) if emb else None

            if existing_id:
                node = self.nodes[existing_id]
                node["mentions"] = node.get("mentions", 0) + 1
                node["updated_at"] = self._now()
                node.setdefault("sources", [])
                if source_ref not in node["sources"]:
                    node["sources"].append(source_ref)
                node_id = existing_id
            else:
                node_id = self._short_id()
                self.nodes[node_id] = {
                    "id": node_id,
                    "type": itype,
                    "value": value,
                    "confidence": confidence,
                    "embedding": emb,
                    "created_at": self._now(),
                    "updated_at": self._now(),
                    "mentions": 1,
                    "sources": [source_ref],
                }
                added += 1

            edge = {
                "from": person_id,
                "to": node_id,
                "relation": _RELATION.get(itype, "related_to"),
                "source": source_ref,
            }
            if edge not in self.edges:
                self.edges.append(edge)

        return added

    def summary(self) -> str:
        counts = Counter(n["type"] for n in self.nodes.values())
        lines = [f"Nodes: {len(self.nodes)}"]
        for t in ("person", "fact", "intent", "emotion", "behavior"):
            if t in counts:
                lines.append(f"  {t}: {counts[t]}")
        lines.append(f"Edges: {len(self.edges)}")
        lines.append(f"Processed messages: {len(self.processed)}")
        return "\n".join(lines)

    def get_person_graph(self, identifier: str) -> Dict:
        """Return all nodes connected to a person node."""
        person_id = None
        for nid, node in self.nodes.items():
            if node["type"] == "person" and node["value"] == identifier:
                person_id = nid
                break
        if person_id is None:
            return {}

        connected: Dict[str, List] = {}
        for edge in self.edges:
            if edge["from"] != person_id:
                continue
            target = self.nodes.get(edge["to"])
            if not target:
                continue
            t = target["type"]
            connected.setdefault(t, []).append(
                {
                    "value": target["value"],
                    "mentions": target.get("mentions", 1),
                    "confidence": target.get("confidence", 0.8),
                }
            )
        return {"person": identifier, "graph": connected}

    def list_persons(self) -> List[Dict]:
        return [
            n for n in self.nodes.values() if n["type"] == "person"
        ]

    def analyze_frequency(self) -> Dict[str, List[Dict]]:
        """
        Аналізує частоту появи сутностей за типами.
        
        Returns:
            Dict з ключами за типами (fact, intent, emotion, behavior)
            та списками сутностей, відсортованих за mentions
        """
        result = {}
        for node_type in ("fact", "intent", "emotion", "behavior"):
            items = [
                {
                    "id": nid,
                    "value": node["value"],
                    "mentions": node.get("mentions", 1),
                    "confidence": node.get("confidence", 0.8),
                    "created_at": node.get("created_at"),
                }
                for nid, node in self.nodes.items()
                if node["type"] == node_type
            ]
            result[node_type] = sorted(items, key=lambda x: -x["mentions"])
        return result

    def remove_noise(self, min_mentions: int = 2, dry_run: bool = False) -> Dict[str, Any]:
        """
        Видаляє рідкісні сутності (шум) з графу.
        
        Args:
            min_mentions: мінімальна кількість згадок для збереження сутності
            dry_run: якщо True, тільки повертає статистику без видалення
            
        Returns:
            Dict зі статистикою видалення
        """
        to_remove = []
        
        for nid, node in self.nodes.items():
            # Не видаляємо person вузли
            if node["type"] == "person":
                continue
            
            mentions = node.get("mentions", 1)
            confidence = float(node.get("confidence", 0.8))
            if mentions < min_mentions or (mentions == 1 and confidence < 0.45):
                to_remove.append({
                    "id": nid,
                    "type": node["type"],
                    "value": node["value"],
                    "mentions": mentions,
                    "confidence": confidence,
                })
        
        if dry_run:
            return {
                "dry_run": True,
                "would_remove": len(to_remove),
                "items": to_remove
            }
        
        # Видаляємо вузли
        for item in to_remove:
            del self.nodes[item["id"]]
        
        # Видаляємо пов'язані ребра
        removed_ids = {item["id"] for item in to_remove}
        self.edges = [
            edge for edge in self.edges
            if edge["from"] not in removed_ids and edge["to"] not in removed_ids
        ]
        
        return {
            "dry_run": False,
            "removed": len(to_remove),
            "items": to_remove
        }

    def consolidate_similar(self, similarity_threshold: float = 0.85, dry_run: bool = False) -> Dict[str, Any]:
        """
        Консолідація схожих сутностей на основі ембедінгів.
        
        Args:
            similarity_threshold: поріг схожості для об'єднання
            dry_run: якщо True, тільки повертає статистику без об'єднання
            
        Returns:
            Dict зі статистикою консолідації
        """
        consolidations = []
        
        # Групуємо за типами
        by_type = {}
        for nid, node in self.nodes.items():
            if node["type"] in ("fact", "intent", "emotion", "behavior"):
                by_type.setdefault(node["type"], []).append((nid, node))
        
        for node_type, nodes in by_type.items():
            # Перевіряємо пари на схожість
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    nid1, node1 = nodes[i]
                    nid2, node2 = nodes[j]
                    
                    emb1 = node1.get("embedding")
                    emb2 = node2.get("embedding")
                    
                    if not emb1 or not emb2:
                        continue
                    
                    similarity = cosine_similarity(emb1, emb2)
                    
                    if similarity >= similarity_threshold:
                        if self._normalize_value(node1["value"]) == self._normalize_value(node2["value"]):
                            similarity = 1.0
                        # Зберігаємо той, що має більше mentions
                        if node1.get("mentions", 1) >= node2.get("mentions", 1):
                            keep_id, remove_id = nid1, nid2
                            keep_node, remove_node = node1, node2
                        else:
                            keep_id, remove_id = nid2, nid1
                            keep_node, remove_node = node2, node1
                        
                        consolidations.append({
                            "type": node_type,
                            "keep_id": keep_id,
                            "keep_value": keep_node["value"],
                            "keep_mentions": keep_node.get("mentions", 1),
                            "remove_id": remove_id,
                            "remove_value": remove_node["value"],
                            "remove_mentions": remove_node.get("mentions", 1),
                            "similarity": similarity
                        })
        
        if dry_run:
            return {
                "dry_run": True,
                "would_consolidate": len(consolidations),
                "items": consolidations
            }
        
        # Виконуємо консолідацію
        removed_ids = set()
        for cons in consolidations:
            remove_id = cons["remove_id"]
            keep_id = cons["keep_id"]
            
            # Додаємо mentions до вузла, що залишається
            self.nodes[keep_id]["mentions"] += cons["remove_mentions"]
            self.nodes[keep_id]["updated_at"] = self._now()
            
            # Видаляємо вузол
            del self.nodes[remove_id]
            removed_ids.add(remove_id)
            
            # Перенаправляємо ребра
            for edge in self.edges:
                if edge["to"] == remove_id:
                    edge["to"] = keep_id
        
        # Видаляємо ребра з видаленими вузлами
        self.edges = [
            edge for edge in self.edges
            if edge["from"] not in removed_ids and edge["to"] not in removed_ids
        ]
        
        return {
            "dry_run": False,
            "consolidated": len(consolidations),
            "items": consolidations
        }

    def find_connections(self, min_similarity: float = 0.75, dry_run: bool = False) -> Dict[str, Any]:
        """
        Знаходить потенційні нові зв'язки між сутностями на основі схожості ембедінгів.
        
        Args:
            min_similarity: мінімальна схожість для створення зв'язку
            dry_run: якщо True, тільки повертає статистику без створення зв'язків
            
        Returns:
            Dict зі статистикою нових зв'язків
        """
        potential_connections = []
        
        # Отримуємо всі вузли з ембедінгами (крім person)
        embed_nodes = [
            (nid, node)
            for nid, node in self.nodes.items()
            if node["type"] in ("fact", "intent", "emotion", "behavior")
            and node.get("embedding")
        ]

        existing_pairs = {
            tuple(sorted((edge["from"], edge["to"])))
            for edge in self.edges
            if edge.get("relation") == "related_to"
        }
        
        # Перевіряємо пари
        for i in range(len(embed_nodes)):
            for j in range(i + 1, len(embed_nodes)):
                nid1, node1 = embed_nodes[i]
                nid2, node2 = embed_nodes[j]

                # Для зниження шуму пов'язуємо тільки різні типи сутностей
                if node1["type"] == node2["type"]:
                    continue
                
                # Пропускаємо якщо зв'язок вже існує
                pair = tuple(sorted((nid1, nid2)))
                if pair in existing_pairs:
                    continue
                
                similarity = cosine_similarity(node1["embedding"], node2["embedding"])

                min_mentions = min(node1.get("mentions", 1), node2.get("mentions", 1))
                dynamic_threshold = min_similarity + (0.05 if min_mentions <= 1 else 0.0)
                if similarity >= dynamic_threshold:
                    potential_connections.append({
                        "from_id": nid1,
                        "from_type": node1["type"],
                        "from_value": node1["value"],
                        "to_id": nid2,
                        "to_type": node2["type"],
                        "to_value": node2["value"],
                        "similarity": similarity
                    })
        
        if dry_run:
            return {
                "dry_run": True,
                "would_connect": len(potential_connections),
                "items": potential_connections
            }
        
        # Створюємо нові зв'язки
        for conn in potential_connections:
            edge = {
                "from": conn["from_id"],
                "to": conn["to_id"],
                "relation": "related_to",
                "source": f"auto_discovery_{self._now()}",
                "similarity": conn["similarity"]
            }
            self.edges.append(edge)
            existing_pairs.add(tuple(sorted((conn["from_id"], conn["to_id"]))))
        
        return {
            "dry_run": False,
            "connected": len(potential_connections),
            "items": potential_connections
        }

    def search_rag(self, query_embedding: List[float], chat_id: Optional[str] = None,
                   min_similarity: float = 0.70, max_results: int = 10,
                   node_types: Optional[List[str]] = None) -> List[Dict]:
        """
        RAG пошук релевантного контексту з Knowledge Graph.
        
        Args:
            query_embedding: ембедінг запиту
            chat_id: фільтр за конкретним чатом (опціонально)
            min_similarity: мінімальна схожість для включення результату
            max_results: максимальна кількість результатів
            node_types: типи вузлів для пошуку (fact, intent, emotion, behavior)
            
        Returns:
            Список релевантних вузлів з інформацією про схожість
        """
        if node_types is None:
            node_types = ["fact", "intent", "emotion", "behavior"]
        
        results = []
        
        for nid, node in self.nodes.items():
            # Фільтруємо за типом
            if node["type"] not in node_types:
                continue
            
            # Фільтруємо за чатом (якщо вказано)
            if chat_id is not None:
                # Перевіряємо чи вузол пов'язаний з особою з цього чату
                person_match = False
                for edge in self.edges:
                    if edge["to"] == nid:
                        from_node = self.nodes.get(edge["from"])
                        if from_node and from_node.get("type") == "person":
                            if from_node.get("chat_id") == chat_id:
                                person_match = True
                                break
                if not person_match:
                    continue
            
            # Перевіряємо наявність ембедінгу
            node_embedding = node.get("embedding")
            if not node_embedding:
                continue
            
            # Рахуємо схожість
            similarity = cosine_similarity(query_embedding, node_embedding)
            
            if similarity >= min_similarity:
                results.append({
                    "id": nid,
                    "type": node["type"],
                    "value": node["value"],
                    "similarity": similarity,
                    "mentions": node.get("mentions", 1),
                    "confidence": node.get("confidence", 0.8),
                    "sources": node.get("sources", [])
                })
        
        # Сортуємо за схожістю та кількістю згадок
        results.sort(key=lambda x: (-x["similarity"], -x["mentions"]))
        
        return results[:max_results]
