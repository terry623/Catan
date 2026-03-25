"""Board geometry and state for Catan.

Handles hex grid, vertices, edges, terrain, number tokens, ports, and robber.
Uses cube coordinates for the hex grid and pre-computed adjacency tables.
"""

import random
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Resource(Enum):
    BRICK = "brick"
    ORE = "ore"
    WOOL = "wool"
    GRAIN = "grain"
    LUMBER = "lumber"


class Terrain(Enum):
    HILLS = "hills"        # → Brick
    MOUNTAINS = "mountains"  # → Ore
    PASTURE = "pasture"    # → Wool
    FIELDS = "fields"      # → Grain
    FOREST = "forest"      # → Lumber
    DESERT = "desert"      # → None


TERRAIN_RESOURCE = {
    Terrain.HILLS: Resource.BRICK,
    Terrain.MOUNTAINS: Resource.ORE,
    Terrain.PASTURE: Resource.WOOL,
    Terrain.FIELDS: Resource.GRAIN,
    Terrain.FOREST: Resource.LUMBER,
    Terrain.DESERT: None,
}

# Standard tile distribution (19 tiles)
STANDARD_TERRAINS = (
    [Terrain.HILLS] * 3 +
    [Terrain.MOUNTAINS] * 3 +
    [Terrain.PASTURE] * 4 +
    [Terrain.FIELDS] * 4 +
    [Terrain.FOREST] * 4 +
    [Terrain.DESERT] * 1
)

# Standard number tokens (placed on non-desert hexes in order)
STANDARD_NUMBERS = [5, 2, 6, 3, 8, 10, 9, 12, 11, 4, 8, 10, 9, 4, 5, 6, 3, 11]

# Probability dots for each number (used by AI for vertex scoring)
NUMBER_DOTS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}

# ---------------------------------------------------------------------------
# Hex grid using cube coordinates (x, y, z) where x + y + z = 0
#
# The 19 hexes of standard Catan arranged in rings:
#   Center (1) + Ring 1 (6) + Ring 2 (12) = 19
#
# Neighbors of (x,y,z) are the 6 adjacent cubes.
# ---------------------------------------------------------------------------

# 6 cube directions
CUBE_DIRS = [
    (1, -1, 0), (1, 0, -1), (0, 1, -1),
    (-1, 1, 0), (-1, 0, 1), (0, -1, 1),
]

def _cube_add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def _generate_hex_positions():
    """Generate the 19 hex positions in cube coordinates.

    We arrange them in a spiral for consistent numbering:
    center, then ring 1 (starting NE going clockwise),
    then ring 2 (starting NE going clockwise).
    """
    positions = [(0, 0, 0)]  # center

    # Ring 1: 6 hexes
    ring1_start = (0, -1, 1)  # start at "north"
    pos = ring1_start
    for d in range(6):
        positions.append(pos)
        pos = _cube_add(pos, CUBE_DIRS[d])
        # After going one direction, the next position is the next ring-1 hex

    # Actually, let's just enumerate by distance from center
    # Ring 1
    ring1 = []
    for d in CUBE_DIRS:
        ring1.append(d)
    positions = [(0,0,0)] + ring1

    # Ring 2
    ring2 = []
    for i in range(6):
        # Corner hex: 2 steps in direction i
        corner = _cube_add(CUBE_DIRS[i], CUBE_DIRS[i])
        ring2.append(corner)
        # Edge hex: 1 step in direction i, 1 step in direction (i+1)%6
        edge = _cube_add(CUBE_DIRS[i], CUBE_DIRS[(i+1)%6])
        ring2.append(edge)

    positions += ring2
    return positions


HEX_POSITIONS = _generate_hex_positions()
HEX_SET = set(HEX_POSITIONS)
HEX_INDEX = {pos: i for i, pos in enumerate(HEX_POSITIONS)}

# ---------------------------------------------------------------------------
# Vertex geometry
#
# Each vertex sits at the junction of exactly 3 hex positions.
# For a hex at (x,y,z), its 6 vertices are between itself and pairs of
# adjacent directions. We identify each vertex by the sorted tuple of the
# 3 hex cube positions it sits between (whether or not they're on the board).
#
#       v0
#      /  \
#    v5    v1
#    |      |
#    v4    v2
#      \  /
#       v3
# ---------------------------------------------------------------------------

def _build_geometry():
    """Build complete vertex and edge geometry."""
    # Each vertex of hex H is between H and two of its neighbors.
    # Vertex i is between H, neighbor[i], and neighbor[(i+5)%6].
    # (This comes from the hex geometry: vertex i is shared by
    #  the hex, the neighbor in direction i, and the neighbor in direction (i-1)%6)

    # Actually, for pointy-top hexes with our direction ordering:
    # The 6 vertices of hex (x,y,z):
    # vertex 0 (top):    between hex, dir[5]=(0,-1,1), dir[0]=(1,-1,0)
    # vertex 1 (top-R):  between hex, dir[0]=(1,-1,0), dir[1]=(1,0,-1)
    # vertex 2 (bot-R):  between hex, dir[1]=(1,0,-1), dir[2]=(0,1,-1)
    # vertex 3 (bottom): between hex, dir[2]=(0,1,-1), dir[3]=(-1,1,0)
    # vertex 4 (bot-L):  between hex, dir[3]=(-1,1,0), dir[4]=(-1,0,1)
    # vertex 5 (top-L):  between hex, dir[4]=(-1,0,1), dir[5]=(0,-1,1)

    vertex_dirs = [
        (5, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5)
    ]

    vertex_set = {}  # frozenset of 3 cube positions → index
    vertices = []
    hex_vertices = {}

    for hi, hpos in enumerate(HEX_POSITIONS):
        hverts = []
        for vi, (d1, d2) in enumerate(vertex_dirs):
            n1 = _cube_add(hpos, CUBE_DIRS[d1])
            n2 = _cube_add(hpos, CUBE_DIRS[d2])
            key = frozenset([hpos, n1, n2])
            if key not in vertex_set:
                vertex_set[key] = len(vertices)
                vertices.append(key)
            hverts.append(vertex_set[key])
        hex_vertices[hi] = hverts

    # Build edges: each hex has 6 edges connecting consecutive vertices
    edge_set = {}
    edges = []
    hex_edges = {}

    for hi in range(len(HEX_POSITIONS)):
        hedges = []
        verts = hex_vertices[hi]
        for i in range(6):
            v1, v2 = verts[i], verts[(i + 1) % 6]
            edge_key = (min(v1, v2), max(v1, v2))
            if edge_key not in edge_set:
                edge_set[edge_key] = len(edges)
                edges.append(edge_key)
            hedges.append(edge_set[edge_key])
        hex_edges[hi] = hedges

    # Vertex adjacency
    vertex_adjacent = {v: set() for v in range(len(vertices))}
    for v1, v2 in edges:
        vertex_adjacent[v1].add(v2)
        vertex_adjacent[v2].add(v1)

    # Vertex → edges mapping
    vertex_edges = {v: [] for v in range(len(vertices))}
    for ei, (v1, v2) in enumerate(edges):
        vertex_edges[v1].append(ei)
        vertex_edges[v2].append(ei)

    return vertices, hex_vertices, vertex_adjacent, edges, edge_set, hex_edges, vertex_edges


# Pre-compute geometry
VERTICES, HEX_VERTICES, VERTEX_ADJACENT, EDGES, EDGE_INDEX, HEX_EDGES, VERTEX_EDGES = _build_geometry()

# Vertex → list of hex indices that are actually on the board
VERTEX_HEXES = {}
for v_idx, hex_positions_set in enumerate(VERTICES):
    VERTEX_HEXES[v_idx] = [HEX_INDEX[pos] for pos in hex_positions_set if pos in HEX_INDEX]


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

def _build_ports():
    """Define 9 standard ports on coastal edges.

    Ports are placed on edges at the boundary of the board.
    We pick specific hex edges that face outward.
    Format: (hex_index, edge_position, port_type)
    edge_position: 0=top-right, 1=right, 2=bottom-right, 3=bottom-left, 4=left, 5=top-left
    """
    port_defs = [
        (0, 0, None),              # 3:1 generic (center, top-right edge)
        (1, 0, Resource.GRAIN),    # 2:1 grain
        (2, 1, None),              # 3:1 generic
        (6, 1, Resource.ORE),      # 2:1 ore
        (12, 2, Resource.WOOL),    # 2:1 wool
        (18, 3, None),             # 3:1 generic
        (17, 3, Resource.BRICK),   # 2:1 brick
        (16, 4, None),             # 3:1 generic
        (10, 5, Resource.LUMBER),  # 2:1 lumber
    ]

    ports = []
    for hi, epos, ptype in port_defs:
        verts = HEX_VERTICES[hi]
        v1 = verts[epos]
        v2 = verts[(epos + 1) % 6]
        ports.append((v1, v2, ptype))
    return ports

PORTS = _build_ports()


# ---------------------------------------------------------------------------
# Display mapping: cube coords → screen row/col for rendering
# ---------------------------------------------------------------------------

def hex_display_pos(hex_idx):
    """Map a hex index to (display_row, display_col) for rendering.

    Returns the row (0-4) and position within that row.
    """
    x, y, z = HEX_POSITIONS[hex_idx]
    # Convert cube to offset coordinates for display
    # row = z + 2 (so z=-2 → row 0, z=2 → row 4)
    # col depends on row
    row = z + 2  # wait, need to verify this mapping

    # Actually, for display we group by z coordinate:
    # z = -2: outer ring top    → not all have z=-2
    # Let's map using the "row" = distance from top

    # Sort hexes by a display order
    # Use (z, x) as sort key for row-major order
    # But our rings don't map cleanly to rows...

    # Better: assign display row/col manually based on the visual layout
    # We need rows of 3,4,5,4,3
    pass


# We'll define display rows explicitly
def _assign_display_rows():
    """Assign each hex to a display row and position for rendering."""
    # Sort hexes into rows based on their cube z-coordinate
    # In our cube system, z ranges from -2 to 2
    # z = -2: 3 hexes (top row)
    # z = -1: 4 hexes
    # z = 0: 5 hexes (middle)
    # z = 1: 4 hexes
    # z = 2: 3 hexes (bottom row)

    rows = {-2: [], -1: [], 0: [], 1: [], 2: []}
    for hi, (x, y, z) in enumerate(HEX_POSITIONS):
        rows[z].append((x, hi))

    display_rows = []
    for z in [-2, -1, 0, 1, 2]:
        sorted_hexes = sorted(rows[z], key=lambda t: t[0])
        hex_indices = [hi for _, hi in sorted_hexes]
        display_rows.append(hex_indices)

    return display_rows

DISPLAY_ROWS = _assign_display_rows()
# Should give us rows of lengths [3, 4, 5, 4, 3]


# ---------------------------------------------------------------------------
# Board class
# ---------------------------------------------------------------------------

class Board:
    """Represents the game board state."""

    def __init__(self, randomize=True):
        self.terrains = list(STANDARD_TERRAINS)
        self.numbers = [0] * 19

        if randomize:
            self._randomize_board()

        # Find desert and place robber
        self.robber_hex = self.terrains.index(Terrain.DESERT)

        # Buildings: vertex_id → (player_index, 'settlement'|'city')
        self.buildings = {}

        # Roads: edge_id → player_index
        self.roads = {}

        # Port vertices
        self.port_vertices = {}
        for v1, v2, ptype in PORTS:
            self.port_vertices[v1] = ptype
            self.port_vertices[v2] = ptype

    def _randomize_board(self):
        """Randomize terrain and number placement."""
        random.shuffle(self.terrains)
        numbers = list(STANDARD_NUMBERS)
        ni = 0
        for hi in range(19):
            if self.terrains[hi] == Terrain.DESERT:
                self.numbers[hi] = 0
            else:
                self.numbers[hi] = numbers[ni]
                ni += 1

    def get_resource(self, hex_index):
        return TERRAIN_RESOURCE[self.terrains[hex_index]]

    def hexes_for_number(self, number):
        return [hi for hi in range(19)
                if self.numbers[hi] == number and hi != self.robber_hex]

    def can_place_settlement(self, vertex, player_idx, setup=False):
        if vertex in self.buildings:
            return False
        for adj_v in VERTEX_ADJACENT[vertex]:
            if adj_v in self.buildings:
                return False
        if not VERTEX_HEXES.get(vertex):
            return False
        if setup:
            return True
        for ei in VERTEX_EDGES[vertex]:
            if self.roads.get(ei) == player_idx:
                return True
        return False

    def can_place_road(self, edge, player_idx, setup_vertex=None):
        if edge in self.roads:
            return False
        v1, v2 = EDGES[edge]
        if setup_vertex is not None:
            return v1 == setup_vertex or v2 == setup_vertex
        for v in (v1, v2):
            bld = self.buildings.get(v)
            if bld and bld[0] == player_idx:
                return True
            if bld and bld[0] != player_idx:
                continue
            for ei in VERTEX_EDGES[v]:
                if ei != edge and self.roads.get(ei) == player_idx:
                    return True
        return False

    def can_place_city(self, vertex, player_idx):
        bld = self.buildings.get(vertex)
        return bld is not None and bld[0] == player_idx and bld[1] == 'settlement'

    def place_settlement(self, vertex, player_idx):
        self.buildings[vertex] = (player_idx, 'settlement')

    def place_city(self, vertex, player_idx):
        self.buildings[vertex] = (player_idx, 'city')

    def place_road(self, edge, player_idx):
        self.roads[edge] = player_idx

    def get_player_ports(self, player_idx):
        ports = set()
        for vertex, (pidx, _) in self.buildings.items():
            if pidx == player_idx and vertex in self.port_vertices:
                ports.add(self.port_vertices[vertex])
        return ports

    def get_valid_settlement_vertices(self, player_idx, setup=False):
        return [v for v in range(len(VERTICES))
                if self.can_place_settlement(v, player_idx, setup)]

    def get_valid_road_edges(self, player_idx, setup_vertex=None):
        return [e for e in range(len(EDGES))
                if self.can_place_road(e, player_idx, setup_vertex)]

    def get_valid_city_vertices(self, player_idx):
        return [v for v in range(len(VERTICES))
                if self.can_place_city(v, player_idx)]

    def longest_road(self, player_idx):
        """Calculate longest road using DFS."""
        player_edges = {e for e, p in self.roads.items() if p == player_idx}
        if not player_edges:
            return 0

        def get_connected(edge, visited):
            v1, v2 = EDGES[edge]
            connected = set()
            for v in (v1, v2):
                bld = self.buildings.get(v)
                if bld and bld[0] != player_idx:
                    continue
                for ei in VERTEX_EDGES[v]:
                    if ei != edge and ei in player_edges and ei not in visited:
                        connected.add(ei)
            return connected

        max_length = 0
        def dfs(edge, visited):
            nonlocal max_length
            max_length = max(max_length, len(visited))
            for next_e in get_connected(edge, visited):
                visited.add(next_e)
                dfs(next_e, visited)
                visited.remove(next_e)

        for start in player_edges:
            dfs(start, {start})
        return max_length

    def vertex_score(self, vertex):
        """Score a vertex for AI (resource diversity + probability)."""
        score = 0
        resources = set()
        for hi in VERTEX_HEXES.get(vertex, []):
            res = self.get_resource(hi)
            if res:
                resources.add(res)
                score += NUMBER_DOTS.get(self.numbers[hi], 0)
        score += len(resources) * 2
        return score
