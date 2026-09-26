"""
The nodes a typed graph argues with, and the paths that lead to them

Nothing here knows what a node is, so the graph may be citations, patents or commits
A walk runs along the edge direction, which the caller sets by which way it writes an edge
"""

from __future__ import annotations

import random
from collections import Counter, deque
from dataclasses import dataclass, field

from src.core.schema import Edge, Lineage, Magnet


@dataclass(frozen=True)
class Settings:
    """
    Everything the algorithm is tuned by, which arrives from a recipe file and never from code
    """

    weights: dict[str, float] = field(default_factory=dict)
    argues: tuple[str, ...] = ()
    # a backbone paper the whole pool cites outranks the field's own landmarks at a power of one
    focus: float = 1.0
    decay: float = 0.5
    knockdown: float = 0.4
    seeds: int = 10
    walks: int = 50
    branch: int = 1


class LeyLine:
    """
    One graph, read twice: once for what it argues with and once for how it got there
    """

    def __init__(
        self,
        edges: list[Edge],
        settings: Settings,
        scores: dict[str, float],
        order: dict[str, float],
        focus: dict[str, float] | None = None,
    ) -> None:
        """
        Holds the graph and the two maps that hold it to what was asked

        Args:
            edges: The typed edges, source pointing at target.
            settings: The weights per edge type and the walk parameters.
            scores: How much each source node counts, usually its closeness to the question.
            order: Where each node sits in time, lowest first.
            focus: How close each target node sits to what was asked, `None` to leave it out.
        """
        self.edges = [e for e in edges if e.source != e.target]
        self.settings = settings
        self.scores = scores
        self.order = order
        self.focus = focus
        self._found: list[Magnet] | None = None

    def magnets(self) -> list[Magnet]:
        """
        How much position mass a node attracts, what share of its mentions that is, where it sits

        A node everything points at as background carries stance near zero and share near zero, so
        the product drops the generic hub. The focus term drops the hub argued about for a reason
        other than this question.

        Returns:
            One entry per node anything takes a position on, strongest first.
        """
        if self._found is not None:
            return self._found
        stance: dict[str, float] = {}
        total: dict[str, float] = {}
        argued: dict[str, Counter[str]] = {}
        seen: set[tuple[str, str, str]] = set()
        for edge in self.edges:
            key = (edge.source, edge.target, edge.intent)
            if key in seen:
                continue
            seen.add(key)
            weight = max(self.scores.get(edge.source, 0.0), 0.0)
            stance[edge.target] = stance.get(edge.target, 0.0) + self._weight(edge.intent) * weight
            total[edge.target] = total.get(edge.target, 0.0) + weight
            if edge.intent in self.settings.argues:
                argued.setdefault(edge.target, Counter())[edge.intent] += 1

        near = max(self.focus.values(), default=1.0) or 1.0 if self.focus else 1.0
        raw: dict[str, tuple[float, float, float]] = {}
        for node, mass in stance.items():
            if mass <= 0.0:
                continue
            share = mass / total[node] if total.get(node) else 0.0
            sits = (
                (max(self.focus.get(node, 0.0), 0.0) / near) ** self.settings.focus
                if self.focus
                else 1.0
            )
            raw[node] = (mass * share * sits, share, sits)
        top = max((v[0] for v in raw.values()), default=1.0) or 1.0
        self._found = sorted(
            (
                Magnet(
                    node=node,
                    weight=value / top,
                    stance=stance[node],
                    share=share,
                    focus=sits,
                    argued=dict(argued.get(node, Counter())),
                )
                for node, (value, share, sits) in raw.items()
            ),
            key=lambda m: -m.weight,
        )
        return self._found

    def lineages(self) -> list[Lineage]:
        """
        Repeated paths under weight decay, kept as paths rather than flattened into a ranking

        Every run knocks down the magnets it already collected, so the next path is pulled toward
        a part of the graph the last one left alone.

        Returns:
            The surviving paths, most magnet mass first.
        """
        adjacent = self.adjacency()
        pull = {m.node: m.weight for m in self.magnets()}
        if not adjacent or not pull:
            return []
        found: dict[tuple[str, ...], Lineage] = {}
        for seed in range(self.settings.seeds):
            rng = random.Random(seed)
            weight = dict(pull)
            for _ in range(self.settings.walks):
                reach = self.reach(adjacent, weight)
                # reach alone roots every path at the oldest node, since it reaches all of them
                live = [n for n, mass in reach.items() if mass > 0.0 and weight.get(n, 0.0) > 0.0]
                if not live:
                    break
                root = max(live, key=lambda n: reach[n] * weight[n])
                path, collected = self.one_walk(root, adjacent, weight, reach, rng)
                if not collected:
                    break
                nodes = sorted(path, key=lambda n: self.order.get(n, 0.0))
                key = tuple(nodes)
                held = found.get(key)
                if held is None:
                    held = Lineage(
                        nodes=nodes,
                        magnets=sorted(collected, key=lambda n: self.order.get(n, 0.0)),
                    )
                    found[key] = held
                held.runs += 1
                for node in collected:
                    weight[node] = weight.get(node, 0.0) * self.settings.knockdown
        return self.prune(list(found.values()), pull)

    def connectors(self, anchors: set[str], limit: int) -> list[str]:
        """
        Nodes that are not anchors but sit on a path between two that are

        One intermediate is A to X to B and two is A to X to Y to B, which is as far as a bridge
        stays legible.

        Args:
            anchors: The nodes the caller asked about.
            limit: The most to return.

        Returns:
            The bridges, the ones closest to what was asked first.
        """
        after: set[str] = set()
        before: set[str] = set()
        for edge in self.edges:
            if edge.source in anchors and edge.target not in anchors:
                after.add(edge.target)
            if edge.target in anchors and edge.source not in anchors:
                before.add(edge.source)
        found = after & before
        for edge in self.edges:
            if edge.source in anchors or edge.target in anchors:
                continue
            if edge.source in after and edge.target in before:
                found.update((edge.source, edge.target))
        return sorted(found, key=lambda n: -self.scores.get(n, 0.0))[:limit]

    def adjacency(self) -> dict[str, list[str]]:
        """
        Target to source, so a walk along it runs in the order the graph was built

        Returns:
            One list of sources per target.
        """
        out: dict[str, list[str]] = {}
        for edge in self.edges:
            held = out.setdefault(edge.target, [])
            if edge.source not in held:
                held.append(edge.source)
        return out

    def reach(self, adjacent: dict[str, list[str]], weight: dict[str, float]) -> dict[str, float]:
        """
        Magnet weight reachable forward from each node, discounted by how many hops away it is

        Without the discount a magnet six hops out counts as much as one directly adjacent, and the
        walk then starts from the oldest node in the graph rather than the one it is built on.

        Args:
            adjacent: Target to source.
            weight: Magnet weight per node, as the current run has knocked it down.

        Returns:
            Reachable mass per node.
        """
        back: dict[str, list[str]] = {}
        for target, sources in adjacent.items():
            for source in sources:
                back.setdefault(source, []).append(target)
        out: dict[str, float] = {}
        for start, mass in weight.items():
            if mass <= 0.0:
                continue
            seen, queue = {start}, deque([(start, 0)])
            while queue:
                node, hops = queue.popleft()
                out[node] = out.get(node, 0.0) + mass * (self.settings.decay**hops)
                for older in back.get(node, ()):
                    if older not in seen:
                        seen.add(older)
                        queue.append((older, hops + 1))
        return out

    def one_walk(
        self,
        root: str,
        adjacent: dict[str, list[str]],
        weight: dict[str, float],
        reach: dict[str, float],
        rng: random.Random,
    ) -> tuple[list[str], dict[str, float]]:
        """
        One path forward from a root, returning what it walked and the magnets on it

        Args:
            root: Where the path starts.
            adjacent: Target to source.
            weight: Magnet weight per node.
            reach: Reachable mass per node.
            rng: The sampler, so repeated runs differ.

        Returns:
            The path and the magnets collected along it.
        """
        visited, collected = {root}, dict[str, float]()
        path, stack = [root], [root]
        while stack:
            node = stack.pop()
            if weight.get(node, 0.0) > 0.0:
                collected[node] = weight[node]
            options = [
                (n, reach.get(n, 0.0)) for n in adjacent.get(node, ()) if reach.get(n, 0.0) > 0.0
            ]
            if not options:
                continue
            keyed = sorted(((rng.random() ** (1.0 / mass), n) for n, mass in options), reverse=True)
            for _, chosen in keyed[: self.settings.branch]:
                if chosen not in visited:
                    visited.add(chosen)
                    path.append(chosen)
                    stack.append(chosen)
        return path, collected

    def prune(self, found: list[Lineage], pull: dict[str, float]) -> list[Lineage]:
        """
        Drops a path contained in a longer one and ranks what is left by the mass it collected

        Args:
            found: Every distinct path the walks took.
            pull: Magnet weight per node.

        Returns:
            The survivors, strongest first.
        """
        kept: list[Lineage] = []
        for lineage in sorted(found, key=lambda line: -len(line.nodes)):
            held = set(lineage.nodes)
            if any(held <= set(other.nodes) for other in kept):
                continue
            kept.append(lineage)
        kept.sort(key=lambda line: -(sum(pull.get(n, 0.0) for n in line.magnets) * line.runs))
        return kept

    def _weight(self, intent: str) -> float:
        """
        What one edge type is worth

        Args:
            intent: The edge type.

        Returns:
            Its weight, zero for a type the settings never named.
        """
        return self.settings.weights.get(intent, 0.0)
