import logging
from typing import Any, List, Tuple, Dict

logger = logging.getLogger("EvolutionMotor.SearchEngine")


class SearchEngine:
    """
    Motor de búsqueda inteligente para productos.
    Soporta: Búsqueda exacta, parcial, difusa (Levenshtein) y por categoría.
    Lógica pura, independiente de la base de datos.
    """

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calcula la distancia de edición entre dos cadenas."""
        if len(s1) < len(s2):
            return SearchEngine.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def similarity(s1: str, s2: str) -> float:
        """Calcula la similitud entre 0 y 1."""
        distance = SearchEngine.levenshtein_distance(s1.lower(), s2.lower())
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        return 1.0 - (distance / max_len)

    @classmethod
    def search_products(
        cls, query: str, products: List[Dict[str, Any]]
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Busca productos basándose en una query.
        Retorna una lista de (score, producto) ordenada por relevancia.
        """
        query = query.lower().strip()
        results = []

        for p in products:
            name = p.get("name", "").lower()
            category = (p.get("category") or "").lower()

            # 1. Coincidencia Exacta (Score: 1.0)
            if query == name:
                results.append((1.0, p))
                continue

            # 2. Coincidencia de Categoría (Score: 0.9)
            if query == category:
                results.append((0.9, p))
                continue

            # 3. Coincidencia Parcial (Contiene la palabra) (Score: 0.8)
            if query in name or query in category:
                results.append((0.8, p))
                continue

            # 4. Coincidencia Difusa (Fuzzy) (Score: 0.0 - 0.7)
            sim = cls.similarity(query, name)
            if sim > 0.6:  # Umbral de tolerancia
                results.append((sim, p))

        # Ordenar por score descendente
        return sorted(results, key=lambda x: x[0], reverse=True)


search_engine = SearchEngine()
