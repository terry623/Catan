"""AI player logic for Catan.

Implements a reasonable strategy for computer opponents:
- Setup: choose highest-scoring vertices
- Building: prioritize settlements > cities > dev cards > roads
- Robber: target leading opponent
- Trading: trade for needed resources
- Discarding: keep resources needed for current goal
"""

import random
from board import (
    Resource, VERTEX_HEXES, VERTEX_ADJACENT, HEX_VERTICES,
    EDGES, VERTEX_EDGES, NUMBER_DOTS,
)
from player import COSTS
from dev_cards import DevCardType
from display import show_ai_action, RESOURCE_ZH
from trading import ai_bank_trade


def ai_choose_setup_settlement(player, board):
    """Choose the best vertex for initial settlement placement."""
    valid = board.get_valid_settlement_vertices(player.index, setup=True)
    if not valid:
        return None

    # Score each vertex
    scored = [(board.vertex_score(v), random.random(), v) for v in valid]
    scored.sort(reverse=True)
    return scored[0][2]


def ai_choose_setup_road(player, board, settlement_vertex):
    """Choose a road adjacent to the just-placed settlement."""
    valid = board.get_valid_road_edges(player.index, setup_vertex=settlement_vertex)
    if not valid:
        return None

    # Prefer roads that lead toward good future settlement spots
    best_edge = None
    best_score = -1

    for edge in valid:
        v1, v2 = tuple(EDGES[edge])
        other_v = v2 if v1 == settlement_vertex else v1
        # Score based on potential settlement locations reachable
        score = 0
        for adj_v in VERTEX_ADJACENT[other_v]:
            if adj_v != settlement_vertex:
                score += board.vertex_score(adj_v)
        score += random.random()  # tiebreak
        if score > best_score:
            best_score = score
            best_edge = edge

    return best_edge


def _get_build_goal(player, board):
    """Determine what the AI should build next, considering board state."""
    valid_settlements = board.get_valid_settlement_vertices(player.index)
    valid_cities = board.get_valid_city_vertices(player.index)

    # If we can place a settlement somewhere, prioritize that
    if player.settlements_left > 0 and valid_settlements:
        return 'settlement'
    # Cities are high value (2VP each)
    if player.cities_left > 0 and valid_cities:
        return 'city'
    # Build roads to reach new settlement spots
    if player.roads_left > 0 and player.settlements_left > 0:
        return 'road'
    # Buy dev cards as fallback
    return 'dev_card'


def _needed_for_goal(player, goal):
    """Calculate additional resources needed for a build goal."""
    if goal not in COSTS:
        return {}
    cost = COSTS[goal]
    needed = {}
    for r, amt in cost.items():
        diff = amt - player.resources[r]
        if diff > 0:
            needed[r] = diff
    return needed


def ai_play_turn(player, board, game):
    """Execute the AI's full turn (after dice roll and resource distribution)."""
    # 1. Play dev cards if beneficial
    if not player.played_dev_card_this_turn and DevCardType.KNIGHT in player.dev_cards:
        our_hexes = set()
        for v, (pidx, _) in board.buildings.items():
            if pidx == player.index:
                for hi in VERTEX_HEXES.get(v, []):
                    our_hexes.add(hi)
        should_play = (board.robber_hex in our_hexes or
                       player.knights_played >= 2 or
                       len([c for c in player.dev_cards if c == DevCardType.KNIGHT]) >= 2)
        if should_play:
            game.play_dev_card(player, DevCardType.KNIGHT)

    if not player.played_dev_card_this_turn:
        if DevCardType.ROAD_BUILDING in player.dev_cards and player.roads_left >= 2:
            game.play_dev_card(player, DevCardType.ROAD_BUILDING)
        elif DevCardType.YEAR_OF_PLENTY in player.dev_cards:
            game.play_dev_card(player, DevCardType.YEAR_OF_PLENTY)
        elif DevCardType.MONOPOLY in player.dev_cards:
            game.play_dev_card(player, DevCardType.MONOPOLY)

    # 2. Try to build (multiple attempts)
    for _ in range(8):
        if not _ai_try_build(player, board, game):
            break


def _ai_try_build(player, board, game):
    """Try to build one thing. Returns True if successful."""

    # 1. Build settlement if possible and affordable
    if player.can_build('settlement'):
        valid = board.get_valid_settlement_vertices(player.index)
        if valid:
            scored = [(board.vertex_score(v), random.random(), v) for v in valid]
            scored.sort(reverse=True)
            game.build_settlement(player, scored[0][2])
            return True

    # 2. Build city if possible and affordable
    if player.can_build('city'):
        valid = board.get_valid_city_vertices(player.index)
        if valid:
            scored = [(board.vertex_score(v), random.random(), v) for v in valid]
            scored.sort(reverse=True)
            game.build_city(player, scored[0][2])
            return True

    # 3. Build road if affordable — expand toward good settlement spots
    if player.can_build('road') and player.roads_left > 0:
        valid = board.get_valid_road_edges(player.index)
        if valid:
            best_edge = _score_road_edges(player, board, valid)
            if best_edge is not None:
                game.build_road(player, best_edge)
                return True

    # 4. Buy dev card
    if player.can_build('dev_card') and game.dev_deck.remaining() > 0:
        game.buy_dev_card(player)
        return True

    # 5. Try trading to afford the best goal
    goal = _get_build_goal(player, board)
    needed = _needed_for_goal(player, goal)
    if needed and player.total_resources() >= 4:
        traded = ai_bank_trade(player, board, needed)
        if traded:
            return True  # Try building again next iteration

    return False


def _score_road_edges(player, board, valid_edges):
    """Score and pick the best road to build."""
    best_edge = None
    best_score = -1

    for edge in valid_edges:
        v1, v2 = EDGES[edge]
        score = 0
        for v in (v1, v2):
            # Direct settlement spot
            if _can_settle_ignoring_roads(v, player.index, board):
                score += board.vertex_score(v) * 3
            # One step away from settlement spot
            for adj in VERTEX_ADJACENT[v]:
                if _can_settle_ignoring_roads(adj, player.index, board):
                    score += board.vertex_score(adj)
        score += random.random()
        if score > best_score:
            best_score = score
            best_edge = edge

    return best_edge


def _can_settle_ignoring_roads(vertex, player_idx, board):
    """Check if vertex could be a settlement spot (ignoring road connectivity)."""
    if vertex in board.buildings:
        return False
    for adj_v in VERTEX_ADJACENT[vertex]:
        if adj_v in board.buildings:
            return False
    if not VERTEX_HEXES.get(vertex):
        return False
    return True


def ai_choose_robber_hex(player, board, players):
    """Choose where to place the robber."""
    # Place on a hex that hurts the leading opponent the most
    best_hex = None
    best_score = -1

    leading_opponent = None
    max_vp = -1
    for p in players:
        if p.index != player.index and p.victory_points() > max_vp:
            max_vp = p.victory_points()
            leading_opponent = p

    for hi in range(19):
        if hi == board.robber_hex:
            continue
        if board.terrains[hi].value == 'desert':
            continue

        score = 0
        dots = NUMBER_DOTS.get(board.numbers[hi], 0)
        for v in HEX_VERTICES[hi]:
            bld = board.buildings.get(v)
            if bld:
                pidx, btype = bld
                if pidx == player.index:
                    score -= dots * 10  # Don't hurt ourselves
                elif leading_opponent and pidx == leading_opponent.index:
                    score += dots * (3 if btype == 'city' else 2)
                else:
                    score += dots

        score += random.random()
        if score > best_score:
            best_score = score
            best_hex = hi

    return best_hex if best_hex is not None else 0


def ai_choose_steal_target(player, board, robber_hex, players):
    """Choose which player to steal from at the robber hex."""
    targets = set()
    for v in HEX_VERTICES[robber_hex]:
        bld = board.buildings.get(v)
        if bld and bld[0] != player.index:
            target_p = players[bld[0]]
            if target_p.total_resources() > 0:
                targets.add(bld[0])

    if not targets:
        return None

    # Steal from the player with the most resources
    target_idx = max(targets, key=lambda pi: players[pi].total_resources())
    return target_idx


def ai_discard_half(player):
    """Discard half of resources (when having >7 on a 7 roll)."""
    total = player.total_resources()
    to_discard = total // 2

    # Discard resources we have the most of
    discarded = {}
    for _ in range(to_discard):
        # Find resource with highest count
        most = max(Resource, key=lambda r: player.resources[r])
        if player.resources[most] > 0:
            player.resources[most] -= 1
            discarded[most] = discarded.get(most, 0) + 1

    if discarded:
        parts = [f"{RESOURCE_ZH[r]}×{a}" for r, a in discarded.items()]
        show_ai_action(player, f"棄掉 {', '.join(parts)}")


def ai_choose_year_of_plenty(player, board=None):
    """Choose 2 resources for Year of Plenty card."""
    # Try to pick resources we need most
    # Simple: pick the 2 resources we have the least of
    needed = {}
    # Try settlement cost first
    for r, amt in COSTS['settlement'].items():
        diff = amt - player.resources[r]
        if diff > 0:
            needed[r] = diff
    if not needed:
        for r, amt in COSTS['city'].items():
            diff = amt - player.resources[r]
            if diff > 0:
                needed[r] = diff

    chosen = []
    for r, amt in sorted(needed.items(), key=lambda x: -x[1]):
        while len(chosen) < 2 and amt > 0:
            chosen.append(r)
            amt -= 1
    while len(chosen) < 2:
        # Pick something useful
        least = min(Resource, key=lambda r: player.resources[r])
        chosen.append(least)

    return chosen[0], chosen[1]


def ai_choose_monopoly_resource(player, players):
    """Choose which resource to monopolize."""
    # Pick the resource that opponents have the most of
    best_res = None
    best_total = -1
    for r in Resource:
        total = sum(p.resources[r] for p in players if p.index != player.index)
        if total > best_total:
            best_total = total
            best_res = r
    return best_res


def ai_choose_road_building_edges(player, board):
    """Choose 2 edges for Road Building dev card."""
    edges = []
    for _ in range(2):
        if player.roads_left <= 0:
            break
        valid = board.get_valid_road_edges(player.index)
        if not valid:
            break
        # Pick best road
        best = max(valid, key=lambda e: (
            sum(board.vertex_score(v) for v in EDGES[e]
                if board.can_place_settlement(v, player.index)) + random.random()
        ))
        board.place_road(best, player.index)
        player.roads_left -= 1
        edges.append(best)
    return edges
