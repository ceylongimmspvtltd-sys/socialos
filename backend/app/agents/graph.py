"""LangGraph-style deterministic graph engine (zero-dependency).

Mirrors the LangGraph StateGraph API shape (add_node / add_edge / add_conditional_edges /
compile / invoke) so swapping to the real langgraph package later is a drop-in change.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Awaitable, Callable, Hashable

START = "__start__"
END = "__end__"
MAX_STEPS = 64


class Graph:
    def __init__(self) -> None:
        self._nodes: dict[str, Callable[[dict], Awaitable[dict] | dict]] = {}
        self._edges: dict[str, str] = {}
        self._conditional: dict[str, tuple[Callable[[dict], Hashable], dict[Hashable, str]]] = {}
        self._entry = START

    def add_node(self, name: str, fn: Callable) -> "Graph":
        if name in (START, END):
            raise ValueError("reserved node name")
        self._nodes[name] = fn
        return self

    def set_entry_point(self, name: str) -> "Graph":
        self._entry = name
        return self

    def add_edge(self, a: str, b: str) -> "Graph":
        self._edges[a] = b
        return self

    def add_conditional_edges(self, source: str, router: Callable[[dict], Hashable],
                              mapping: dict[Hashable, str]) -> "Graph":
        self._conditional[source] = (router, mapping)
        return self

    def compile(self) -> "CompiledGraph":
        return CompiledGraph(self)


class CompiledGraph:
    def __init__(self, g: Graph) -> None:
        self.g = g

    async def ainvoke(self, state: dict, **kwargs) -> dict:
        node = self.g._entry
        trace: list[str] = []
        for _ in range(MAX_STEPS):
            if node == END:
                break
            if node not in self.g._nodes:
                raise RuntimeError(f"graph references unknown node '{node}'")
            fn = self.g._nodes[node]
            state = await _maybe_await(fn(state, **kwargs)) if _accepts_kwargs(fn) else await _maybe_await(fn(state))
            state.setdefault("trace", []).append(node)
            trace.append(node)
            if node in self.g._conditional:
                router, mapping = self.g._conditional[node]
                key = router(state)
                node = mapping[key]
            elif node in self.g._edges:
                node = self.g._edges[node]
            else:
                node = END
        state["steps"] = trace
        return state

    # LangGraph-compatible alias
    invoke = ainvoke


async def _maybe_await(v: Any) -> Any:
    if hasattr(v, "__await__"):
        return await v
    return v


def _accepts_kwargs(fn: Callable) -> bool:
    import inspect

    try:
        sig = inspect.signature(fn)
        return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    except (TypeError, ValueError):
        return False
