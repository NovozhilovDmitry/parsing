import math


def bellman_ford(graph, start):
    distances = {node: float('inf') for node in graph}
    predecessors = {node: None for node in graph}
    distances[start] = 0

    for _ in range(len(graph) - 1):
        for node in graph:
            for neighbor, weight in graph[node]:
                if distances[node] + weight < distances[neighbor]:
                    distances[neighbor] = distances[node] + weight
                    predecessors[neighbor] = node

    for node in graph:
        for neighbor, weight in graph[node]:
            if distances[node] + weight < distances[neighbor]:
                cycle = []
                visited = set()
                current = node
                while current not in visited:
                    visited.add(current)
                    current = predecessors[current]
                cycle_start = current

                cycle = [cycle_start]
                current = predecessors[cycle_start]
                while current != cycle_start:
                    cycle.append(current)
                    current = predecessors[current]
                cycle.append(cycle_start)
                cycle.reverse()

                return cycle  # Возвращаем найденный цикл

    return None  # Нет арбитража


def build_graph(prices: dict, base_currency: str, fee_rate: float, min_liquidity: float):
    graph = {}

    for pair, price_data in prices.items():
        bid, ask = price_data["bid"], price_data["ask"]
        bid_size, ask_size = price_data["bidSize"], price_data["askSize"]
        if bid is not None and ask is not None and bid_size is not None and ask_size is not None:
            base = base_currency
            coin = pair.replace(base_currency, '')

            if base not in graph:
                graph[base] = []
            if coin not in graph:
                graph[coin] = []

            # Проверяем ликвидность перед добавлением рёбер
            if ask * ask_size >= min_liquidity:
                graph[base].append((coin, -math.log(ask * (1 - fee_rate))))

            if bid * bid_size >= min_liquidity:
                graph[coin].append((base, math.log(bid * (1 - fee_rate))))

    return graph