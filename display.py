"""Terminal display for Catan board game.

Renders the hex board, player info, and menus with ANSI colors.
All user-facing text is in Traditional Chinese (繁體中文).
"""

import os
from board import (
    Resource, Terrain, HEX_POSITIONS, HEX_VERTICES, VERTEX_HEXES,
    VERTEX_ADJACENT, EDGES, EDGE_INDEX, VERTICES, NUMBER_DOTS, PORTS,
    DISPLAY_ROWS,
)
from dev_cards import DevCardType, CARD_NAMES_ZH

# ---------------------------------------------------------------------------
# ANSI Color codes
# ---------------------------------------------------------------------------

class C:
    """ANSI color constants."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    # Player colors
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"

    # Terrain/resource colors
    BRICK_C   = "\033[31m"     # dark red
    ORE_C     = "\033[37m"     # gray/white
    WOOL_C    = "\033[92m"     # light green
    GRAIN_C   = "\033[93m"     # yellow
    LUMBER_C  = "\033[32m"     # dark green
    DESERT_C  = "\033[33m"     # brown/dark yellow

    # Background colors for hexes
    BG_BRICK   = "\033[41m"
    BG_ORE     = "\033[100m"
    BG_WOOL    = "\033[42m"
    BG_GRAIN   = "\033[43m"
    BG_LUMBER  = "\033[42m"
    BG_DESERT  = "\033[43m"

    WHITE   = "\033[97m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"


PLAYER_COLOR_CODES = {
    'red': C.RED,
    'blue': C.BLUE,
    'green': C.GREEN,
    'yellow': C.YELLOW,
}

TERRAIN_ZH = {
    Terrain.HILLS: "磚",
    Terrain.MOUNTAINS: "礦",
    Terrain.PASTURE: "毛",
    Terrain.FIELDS: "麥",
    Terrain.FOREST: "木",
    Terrain.DESERT: "沙",
}

TERRAIN_COLOR = {
    Terrain.HILLS: C.BRICK_C,
    Terrain.MOUNTAINS: C.ORE_C,
    Terrain.PASTURE: C.WOOL_C,
    Terrain.FIELDS: C.GRAIN_C,
    Terrain.FOREST: C.LUMBER_C,
    Terrain.DESERT: C.DESERT_C,
}

RESOURCE_ZH = {
    Resource.BRICK: "磚塊",
    Resource.ORE: "礦石",
    Resource.WOOL: "羊毛",
    Resource.GRAIN: "麥子",
    Resource.LUMBER: "木材",
}

RESOURCE_COLOR = {
    Resource.BRICK: C.BRICK_C,
    Resource.ORE: C.ORE_C,
    Resource.WOOL: C.WOOL_C,
    Resource.GRAIN: C.GRAIN_C,
    Resource.LUMBER: C.LUMBER_C,
}


def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def colored(text, color_code):
    return f"{color_code}{text}{C.RESET}"


def player_colored(text, player):
    return colored(text, PLAYER_COLOR_CODES[player.color])


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

# We render the board as a grid of hex cells.
# Each hex is drawn as:
#    ╱‾‾‾╲
#   │ T nn│
#    ╲___╱
#
# Where T = terrain char, nn = number
#
# Hexes are staggered: odd rows offset right.
# Our hex layout (rows of 3,4,5,4,3) maps to display rows.

# Board layout: use DISPLAY_ROWS from board.py with x-offsets for staggering
BOARD_ROWS = [
    (DISPLAY_ROWS[0], 2),  # 3 hexes
    (DISPLAY_ROWS[1], 1),  # 4 hexes
    (DISPLAY_ROWS[2], 0),  # 5 hexes
    (DISPLAY_ROWS[3], 1),  # 4 hexes
    (DISPLAY_ROWS[4], 2),  # 3 hexes
]


def _render_hex_cell(board, hex_idx, robber_hex):
    """Render a single hex as 3 lines of text (no color codes for width calc)."""
    terrain = board.terrains[hex_idx]
    number = board.numbers[hex_idx]
    t_char = TERRAIN_ZH[terrain]
    t_color = TERRAIN_COLOR[terrain]

    is_robber = (hex_idx == robber_hex)

    if number == 0:
        n_str = "  "
        n_colored = "  "
    else:
        n_str = f"{number:2d}"
        if number in (6, 8):
            n_colored = colored(f"{C.BOLD}{n_str}", C.RED)
        else:
            n_colored = n_str

    robber_str = colored("盜", C.MAGENTA) if is_robber else "  "

    # 3 lines
    # Line 0:  ╱‾‾‾‾‾╲
    # Line 1: │ T nn R │
    # Line 2:  ╲______╱
    line0 = f"  /‾‾‾‾‾\\  "
    line1_content = f" {t_color}{t_char}{C.RESET} {n_colored} {robber_str}"
    line1 = f"| {line1_content} |"
    line2 = f"  \\_____/  "

    return [line0, line1, line2]


def render_board(board, players=None):
    """Render the full board as a string."""
    lines = []
    lines.append("")
    lines.append(colored("  ═══════════ 卡 坦 島 ═══════════", C.BOLD + C.CYAN))
    lines.append("")

    # Render hex index header for reference
    for row_hexes, x_offset in BOARD_ROWS:
        prefix = "  " * x_offset
        # Top borders
        top_parts = []
        mid_parts = []
        bot_parts = []
        for hi in row_hexes:
            terrain = board.terrains[hi]
            number = board.numbers[hi]
            t_char = TERRAIN_ZH[terrain]
            t_color = TERRAIN_COLOR[terrain]
            is_robber = (hi == board.robber_hex)

            if number == 0:
                n_colored = "  "
            elif number in (6, 8):
                n_colored = colored(f"{number:2d}", C.BOLD + C.RED)
            else:
                n_colored = f"{number:2d}"

            robber_mark = colored("盜", C.MAGENTA + C.BOLD) if is_robber else "  "
            hi_str = colored(f"{hi:2d}", C.DIM)

            top_parts.append(f" /‾‾‾‾\\ ")
            mid_parts.append(f"|{t_color}{t_char}{C.RESET} {n_colored}{robber_mark}|")
            bot_parts.append(f" \\____/ ")

        lines.append(prefix + "  ".join(top_parts))
        lines.append(prefix + "  ".join(mid_parts))
        lines.append(prefix + "  ".join(bot_parts))

    lines.append("")

    # Show buildings (settlements and cities) with vertex IDs
    if players and board.buildings:
        lines.append(colored("  建築物:", C.BOLD))
        for v, (pidx, btype) in sorted(board.buildings.items()):
            p = players[pidx]
            b_zh = "聚落" if btype == 'settlement' else "城市"
            # Show which hexes this vertex touches
            hex_nums = []
            for hi in VERTEX_HEXES.get(v, []):
                if board.numbers[hi] > 0:
                    hex_nums.append(str(board.numbers[hi]))
            hex_info = ",".join(hex_nums) if hex_nums else "-"
            lines.append(f"    {player_colored(f'● {p.name}', p)} {b_zh} (節點{v}, 相鄰數字:{hex_info})")

    # Show roads
    if players and board.roads:
        lines.append(colored("  道路:", C.BOLD))
        road_counts = {}
        for e, pidx in board.roads.items():
            road_counts[pidx] = road_counts.get(pidx, 0) + 1
        for pidx, count in sorted(road_counts.items()):
            p = players[pidx]
            lines.append(f"    {player_colored(f'━ {p.name}', p)} × {count}")

    lines.append("")
    return "\n".join(lines)


def render_player_info(player, is_current=False):
    """Render player's status info."""
    lines = []
    marker = "▶ " if is_current else "  "
    pc = PLAYER_COLOR_CODES[player.color]

    header = f"{marker}{pc}{C.BOLD}{player.name}{C.RESET}"
    vp = player.victory_points()
    header += f"  VP:{vp}"
    if player.has_longest_road:
        header += colored(" [最長道路]", C.CYAN)
    if player.has_largest_army:
        header += colored(" [最大騎士團]", C.CYAN)
    lines.append(header)

    if player.is_human or is_current:
        # Show resources
        res_parts = []
        for r in Resource:
            amt = player.resources[r]
            rc = RESOURCE_COLOR[r]
            rname = RESOURCE_ZH[r]
            res_parts.append(f"{rc}{rname}{C.RESET}:{amt}")
        lines.append("    " + " ".join(res_parts))

        # Show dev cards
        if player.dev_cards or player.new_dev_cards:
            card_strs = []
            for card in player.dev_cards:
                card_strs.append(CARD_NAMES_ZH[card])
            for card in player.new_dev_cards:
                card_strs.append(f"[{CARD_NAMES_ZH[card]}](新)")
            lines.append(f"    發展卡: {', '.join(card_strs)}")
    else:
        # For AI, show limited info
        lines.append(f"    手牌:{player.total_resources()} 發展卡:{len(player.dev_cards) + len(player.new_dev_cards)}")

    remaining = f"聚落:{player.settlements_left} 城市:{player.cities_left} 道路:{player.roads_left}"
    lines.append(f"    {remaining}")

    return "\n".join(lines)


def render_all_players(players, current_idx):
    """Render info for all players."""
    lines = [colored("  ─── 玩家資訊 ───", C.BOLD)]
    for p in players:
        lines.append(render_player_info(p, is_current=(p.index == current_idx)))
    lines.append("")
    return "\n".join(lines)


def show_dice_roll(d1, d2):
    total = d1 + d2
    return f"  🎲 擲骰: [{d1}] + [{d2}] = {C.BOLD}{total}{C.RESET}"


def show_resource_production(distributions):
    """Show what resources each player got."""
    lines = []
    if not distributions:
        lines.append("  沒有人獲得資源。")
    else:
        for player, resource, amount in distributions:
            rc = RESOURCE_COLOR[resource]
            rname = RESOURCE_ZH[resource]
            lines.append(f"    {player_colored(player.name, player)} 獲得 {rc}{amount} {rname}{C.RESET}")
    return "\n".join(lines)


def prompt_choice(prompt_text, options, allow_cancel=True):
    """Display numbered options and get user choice.

    Args:
        prompt_text: The prompt to display
        options: list of (value, display_text) tuples
        allow_cancel: if True, add a cancel option

    Returns:
        The chosen value, or None if cancelled
    """
    print(f"\n  {C.BOLD}{prompt_text}{C.RESET}")
    for i, (val, text) in enumerate(options):
        print(f"    {C.CYAN}{i+1}{C.RESET}. {text}")
    if allow_cancel:
        print(f"    {C.CYAN}0{C.RESET}. 取消")

    while True:
        try:
            raw = input(f"\n  請選擇 [{'0-' if allow_cancel else '1-'}{len(options)}]: ").strip()
            if not raw:
                continue
            choice = int(raw)
            if allow_cancel and choice == 0:
                return None
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
            print("  無效選擇，請重試。")
        except (ValueError, EOFError):
            print("  請輸入數字。")


def prompt_yes_no(question):
    """Ask a yes/no question."""
    while True:
        try:
            raw = input(f"  {question} (y/n): ").strip().lower()
            if raw in ('y', 'yes', '是'):
                return True
            if raw in ('n', 'no', '否'):
                return False
        except EOFError:
            return False


def show_message(msg):
    print(f"  {msg}")


def show_ai_action(player, action_text):
    pc = PLAYER_COLOR_CODES[player.color]
    print(f"  {pc}{player.name}{C.RESET}: {action_text}")


def press_enter():
    try:
        input(f"  {C.DIM}按 Enter 繼續...{C.RESET}")
    except EOFError:
        pass


def show_port_info(board):
    """Show port information."""
    lines = [colored("  港口:", C.BOLD)]
    for v1, v2, ptype in PORTS:
        if ptype is None:
            pname = "3:1 通用港"
        else:
            pname = f"2:1 {RESOURCE_ZH[ptype]}港"
        lines.append(f"    節點 {v1},{v2}: {pname}")
    return "\n".join(lines)
