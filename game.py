"""Game engine for Catan — manages turn flow, rules, and win conditions."""

import random
from board import (
    Board, Resource, VERTEX_HEXES, HEX_VERTICES, EDGES, VERTEX_EDGES,
    NUMBER_DOTS,
)
from player import HumanPlayer, AIPlayer, COSTS
from dev_cards import DevCardDeck, DevCardType, CARD_NAMES_ZH
from display import (
    clear_screen, render_board, render_all_players, show_dice_roll,
    show_resource_production, prompt_choice, prompt_yes_no, show_message,
    show_ai_action, press_enter, C, colored, player_colored,
    RESOURCE_ZH, RESOURCE_COLOR, show_port_info,
)
from trading import bank_trade, player_trade_with_ai
from ai import (
    ai_choose_setup_settlement, ai_choose_setup_road, ai_play_turn,
    ai_choose_robber_hex, ai_choose_steal_target, ai_discard_half,
    ai_choose_year_of_plenty, ai_choose_monopoly_resource,
    ai_choose_road_building_edges,
)


class Game:
    """Main game controller."""

    def __init__(self, num_ai=3):
        self.board = Board(randomize=True)
        self.dev_deck = DevCardDeck()
        self.num_players = 1 + num_ai

        # Create players: index 0 = human, rest = AI
        self.players = [HumanPlayer(0)]
        for i in range(1, self.num_players):
            self.players.append(AIPlayer(i))

        self.current_player_idx = 0
        self.turn_number = 0
        self.longest_road_player = None
        self.largest_army_player = None
        self.game_over = False
        self.winner = None

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def show_state(self):
        clear_screen()
        print(render_board(self.board, self.players))
        print(render_all_players(self.players, self.current_player_idx))

    # ------------------------------------------------------------------
    # Setup phase
    # ------------------------------------------------------------------

    def setup_phase(self):
        """Handle the initial settlement/road placement (snake draft)."""
        clear_screen()
        print(colored("\n  ═══ 建設階段 ═══\n", C.BOLD + C.CYAN))
        print(render_board(self.board, self.players))
        print("  每位玩家輪流放置 2 個聚落和 2 條道路。")
        print("  第二輪順序相反（蛇形選位）。")
        press_enter()

        # Snake draft: 0,1,2,3,3,2,1,0
        order = list(range(self.num_players))
        draft_order = order + list(reversed(order))

        for round_num, pidx in enumerate(draft_order):
            player = self.players[pidx]
            is_second = (round_num >= self.num_players)

            self.current_player_idx = pidx
            self.show_state()

            round_label = "第二個" if is_second else "第一個"
            show_message(colored(
                f"── {player_colored(player.name, player)} 放置{round_label}聚落 ──",
                C.BOLD))

            # Place settlement
            vertex = self._setup_place_settlement(player)
            if vertex is None:
                show_message("錯誤：無法放置聚落！")
                continue

            self.board.place_settlement(vertex, player.index)
            player.settlements_left -= 1

            # Second settlement grants initial resources
            if is_second:
                for hi in VERTEX_HEXES.get(vertex, []):
                    res = self.board.get_resource(hi)
                    if res:
                        player.add_resource(res)

            self.show_state()

            # Place road
            edge = self._setup_place_road(player, vertex)
            if edge is not None:
                self.board.place_road(edge, player.index)
                player.roads_left -= 1

            if player.is_human:
                press_enter()

    def _setup_place_settlement(self, player):
        """Place a settlement during setup phase."""
        valid = self.board.get_valid_settlement_vertices(player.index, setup=True)
        if not valid:
            return None

        if player.is_human:
            options = []
            for v in sorted(valid):
                hex_info = []
                for hi in VERTEX_HEXES.get(v, []):
                    terrain = self.board.terrains[hi]
                    num = self.board.numbers[hi]
                    from display import TERRAIN_ZH
                    t_name = TERRAIN_ZH[terrain]
                    dots = NUMBER_DOTS.get(num, 0)
                    if num > 0:
                        hex_info.append(f"{t_name}{num}({dots}點)")
                    else:
                        hex_info.append(f"{t_name}")
                score = self.board.vertex_score(v)
                desc = f"節點{v}: {', '.join(hex_info)}  (分數:{score})"
                options.append((v, desc))
            # Sort by score descending
            options.sort(key=lambda x: -self.board.vertex_score(x[0]))
            return prompt_choice("選擇聚落位置:", options, allow_cancel=False)
        else:
            v = ai_choose_setup_settlement(player, self.board)
            if v is not None:
                hex_info = []
                for hi in VERTEX_HEXES.get(v, []):
                    num = self.board.numbers[hi]
                    if num > 0:
                        hex_info.append(str(num))
                show_ai_action(player, f"放置聚落於節點{v} (相鄰:{','.join(hex_info)})")
            return v

    def _setup_place_road(self, player, settlement_vertex):
        """Place a road during setup phase."""
        valid = self.board.get_valid_road_edges(player.index, setup_vertex=settlement_vertex)
        if not valid:
            return None

        if player.is_human:
            options = []
            for e in valid:
                v1, v2 = tuple(EDGES[e])
                options.append((e, f"道路 {v1}↔{v2}"))
            return prompt_choice("選擇道路位置:", options, allow_cancel=False)
        else:
            e = ai_choose_setup_road(player, self.board, settlement_vertex)
            if e is not None:
                v1, v2 = tuple(EDGES[e])
                show_ai_action(player, f"放置道路 {v1}↔{v2}")
            return e

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    def play(self):
        """Main game loop."""
        self.setup_phase()

        self.current_player_idx = 0
        self.turn_number = 1

        while not self.game_over:
            player = self.players[self.current_player_idx]
            self._play_turn(player)

            if self.game_over:
                break

            # End of turn
            player.end_turn_cards()
            self.current_player_idx = (self.current_player_idx + 1) % self.num_players
            if self.current_player_idx == 0:
                self.turn_number += 1

        # Game over
        self.show_state()
        print(colored(f"\n  🏆 遊戲結束！{player_colored(self.winner.name, self.winner)} 獲勝！"
                       f" (勝利點數: {self.winner.victory_points()})\n", C.BOLD + C.CYAN))

    def _play_turn(self, player):
        """Execute one player's turn."""
        self.show_state()

        if player.is_human:
            self._human_turn(player)
        else:
            self._ai_turn(player)

    # ------------------------------------------------------------------
    # Human turn
    # ------------------------------------------------------------------

    def _human_turn(self, player):
        """Handle human player's turn."""
        show_message(colored(f"══ 第 {self.turn_number} 回合 — 你的回合 ══", C.BOLD + C.CYAN))

        # Pre-roll: option to play dev card
        if self._has_playable_dev_card(player):
            if prompt_yes_no("擲骰前要使用發展卡嗎?"):
                self._human_play_dev_card(player)
                self.show_state()

        # Roll dice
        input(f"  按 Enter 擲骰子...")
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        print(show_dice_roll(d1, d2))

        # Handle roll
        if total == 7:
            self._handle_seven(player)
        else:
            self._distribute_resources(total)

        press_enter()

        # Action phase
        while True:
            self.show_state()
            action_options = [
                ('build', "建造"),
                ('trade', "交易"),
            ]
            if self._has_playable_dev_card(player):
                action_options.append(('dev_card', "使用發展卡"))
            action_options.append(('ports', "查看港口"))
            action_options.append(('end', "結束回合"))

            action = prompt_choice("選擇行動:", action_options, allow_cancel=False)

            if action == 'end':
                break
            elif action == 'build':
                self._human_build(player)
            elif action == 'trade':
                self._human_trade(player)
            elif action == 'dev_card':
                self._human_play_dev_card(player)
            elif action == 'ports':
                print(show_port_info(self.board))
                press_enter()

            # Check victory
            if self._check_victory(player):
                return

    def _human_build(self, player):
        """Handle build menu for human player."""
        options = []
        if player.can_build('road'):
            valid_roads = self.board.get_valid_road_edges(player.index)
            if valid_roads:
                options.append(('road', f"道路 (磚×1, 木×1) — 可建{len(valid_roads)}處"))
        if player.can_build('settlement'):
            valid_sett = self.board.get_valid_settlement_vertices(player.index)
            if valid_sett:
                options.append(('settlement', f"聚落 (磚×1, 木×1, 毛×1, 麥×1) — 可建{len(valid_sett)}處"))
        if player.can_build('city'):
            valid_city = self.board.get_valid_city_vertices(player.index)
            if valid_city:
                options.append(('city', f"城市 (麥×2, 礦×3) — 可升級{len(valid_city)}處"))
        if player.can_build('dev_card') and self.dev_deck.remaining() > 0:
            options.append(('dev_card', f"發展卡 (礦×1, 毛×1, 麥×1) — 剩餘{self.dev_deck.remaining()}張"))

        if not options:
            show_message("你目前無法建造任何東西。")
            return

        choice = prompt_choice("建造什麼?", options)
        if choice is None:
            return

        if choice == 'road':
            valid = self.board.get_valid_road_edges(player.index)
            edge_options = []
            for e in valid:
                v1, v2 = tuple(EDGES[e])
                edge_options.append((e, f"道路 {v1}↔{v2}"))
            edge = prompt_choice("選擇道路位置:", edge_options)
            if edge is not None:
                self.build_road(player, edge)

        elif choice == 'settlement':
            valid = self.board.get_valid_settlement_vertices(player.index)
            vert_options = []
            for v in sorted(valid):
                hex_info = []
                for hi in VERTEX_HEXES.get(v, []):
                    num = self.board.numbers[hi]
                    if num > 0:
                        hex_info.append(str(num))
                desc = f"節點{v} (相鄰:{','.join(hex_info) if hex_info else '-'})"
                vert_options.append((v, desc))
            vertex = prompt_choice("選擇聚落位置:", vert_options)
            if vertex is not None:
                self.build_settlement(player, vertex)

        elif choice == 'city':
            valid = self.board.get_valid_city_vertices(player.index)
            city_options = []
            for v in valid:
                hex_info = []
                for hi in VERTEX_HEXES.get(v, []):
                    num = self.board.numbers[hi]
                    if num > 0:
                        hex_info.append(str(num))
                desc = f"節點{v} (相鄰:{','.join(hex_info) if hex_info else '-'})"
                city_options.append((v, desc))
            vertex = prompt_choice("選擇升級為城市的聚落:", city_options)
            if vertex is not None:
                self.build_city(player, vertex)

        elif choice == 'dev_card':
            self.buy_dev_card(player)

    def _human_trade(self, player):
        """Handle trade menu for human player."""
        options = [
            ('bank', "銀行/港口交易"),
            ('player', "與電腦玩家交易"),
        ]
        choice = prompt_choice("交易方式:", options)
        if choice == 'bank':
            bank_trade(player, self.board)
        elif choice == 'player':
            ai_players = [p for p in self.players if not p.is_human]
            player_trade_with_ai(player, ai_players, self.board)

    def _human_play_dev_card(self, player):
        """Handle playing a development card."""
        if player.played_dev_card_this_turn:
            show_message("你這回合已經使用過發展卡了。")
            return

        playable = [(c, CARD_NAMES_ZH[c]) for c in player.dev_cards
                     if c != DevCardType.VICTORY_POINT]
        if not playable:
            show_message("你沒有可使用的發展卡。")
            return

        # Deduplicate
        seen = {}
        options = []
        for card, name in playable:
            if card not in seen:
                count = player.dev_cards.count(card)
                options.append((card, f"{name} (×{count})"))
                seen[card] = True

        card = prompt_choice("使用哪張發展卡?", options)
        if card is not None:
            self.play_dev_card(player, card)

    def _has_playable_dev_card(self, player):
        """Check if player has any playable dev cards."""
        if player.played_dev_card_this_turn:
            return False
        return any(c != DevCardType.VICTORY_POINT for c in player.dev_cards)

    # ------------------------------------------------------------------
    # AI turn
    # ------------------------------------------------------------------

    def _ai_turn(self, player):
        """Handle AI player's turn."""
        show_message(colored(
            f"── {player_colored(player.name, player)} 的回合 ──", C.BOLD))

        # Roll dice
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        print(show_dice_roll(d1, d2))

        if total == 7:
            self._handle_seven(player)
        else:
            self._distribute_resources(total)

        # AI actions
        ai_play_turn(player, self.board, self)

        # Check victory
        self._check_victory(player)

        press_enter()

    # ------------------------------------------------------------------
    # Resource distribution
    # ------------------------------------------------------------------

    def _distribute_resources(self, number):
        """Distribute resources for a dice roll."""
        distributions = []
        active_hexes = self.board.hexes_for_number(number)

        for hi in active_hexes:
            res = self.board.get_resource(hi)
            if res is None:
                continue
            for v in HEX_VERTICES[hi]:
                bld = self.board.buildings.get(v)
                if bld:
                    pidx, btype = bld
                    amt = 2 if btype == 'city' else 1
                    self.players[pidx].add_resource(res, amt)
                    distributions.append((self.players[pidx], res, amt))

        print(show_resource_production(distributions))

    # ------------------------------------------------------------------
    # Robber (rolling 7)
    # ------------------------------------------------------------------

    def _handle_seven(self, player):
        """Handle rolling a 7: discard, move robber, steal."""
        show_message(colored("出現 7！強盜來襲！", C.BOLD + C.RED))

        # All players with >7 cards must discard half
        for p in self.players:
            if p.total_resources() > 7:
                show_message(f"{player_colored(p.name, p)} 有 {p.total_resources()} 張牌，必須棄掉一半。")
                if p.is_human:
                    self._human_discard_half(p)
                else:
                    ai_discard_half(p)

        # Active player moves robber
        if player.is_human:
            self._human_move_robber(player)
        else:
            self._ai_move_robber(player)

    def _human_discard_half(self, player):
        """Human player discards half their resources."""
        total = player.total_resources()
        to_discard = total // 2
        show_message(f"你需要棄掉 {to_discard} 張資源牌。")

        discarded = 0
        while discarded < to_discard:
            remaining = to_discard - discarded
            options = []
            for r in Resource:
                if player.resources[r] > 0:
                    rc = RESOURCE_COLOR[r]
                    options.append((r, f"{rc}{RESOURCE_ZH[r]}{C.RESET} (持有:{player.resources[r]})"))

            show_message(f"還需棄掉 {remaining} 張:")
            res = prompt_choice("棄掉哪種資源?", options, allow_cancel=False)
            if res is not None:
                player.resources[res] -= 1
                discarded += 1

    def _human_move_robber(self, player):
        """Human player moves the robber."""
        options = []
        for hi in range(19):
            if hi == self.board.robber_hex:
                continue
            terrain = self.board.terrains[hi]
            from display import TERRAIN_ZH
            t_name = TERRAIN_ZH[terrain]
            num = self.board.numbers[hi]
            # Show who has buildings there
            occupants = []
            for v in HEX_VERTICES[hi]:
                bld = self.board.buildings.get(v)
                if bld:
                    p = self.players[bld[0]]
                    occupants.append(p.name)
            occ_str = f" [{', '.join(occupants)}]" if occupants else ""
            desc = f"格{hi}: {t_name} {num if num else '-'}{occ_str}"
            options.append((hi, desc))

        hex_choice = prompt_choice("把強盜移到哪裡?", options, allow_cancel=False)
        if hex_choice is not None:
            self.board.robber_hex = hex_choice
            show_message(f"強盜已移至格{hex_choice}。")
            self._steal_resource(player, hex_choice)

    def _ai_move_robber(self, player):
        """AI moves the robber."""
        hex_choice = ai_choose_robber_hex(player, self.board, self.players)
        self.board.robber_hex = hex_choice
        show_ai_action(player, f"移動強盜至格{hex_choice}")
        self._steal_resource(player, hex_choice)

    def _steal_resource(self, player, robber_hex):
        """Steal a resource from a player at the robber hex."""
        if player.is_human:
            # Show steal targets
            targets = set()
            for v in HEX_VERTICES[robber_hex]:
                bld = self.board.buildings.get(v)
                if bld and bld[0] != player.index:
                    target_p = self.players[bld[0]]
                    if target_p.total_resources() > 0:
                        targets.add(bld[0])

            if not targets:
                show_message("沒有可以偷取的對象。")
                return

            if len(targets) == 1:
                target_idx = targets.pop()
            else:
                options = [(pi, player_colored(self.players[pi].name, self.players[pi]))
                           for pi in targets]
                target_idx = prompt_choice("偷取誰的資源?", options, allow_cancel=False)
                if target_idx is None:
                    return
        else:
            target_idx = ai_choose_steal_target(player, self.board, robber_hex, self.players)
            if target_idx is None:
                return

        target = self.players[target_idx]
        # Steal random resource
        available = [r for r in Resource for _ in range(target.resources[r])]
        if available:
            stolen = random.choice(available)
            target.resources[stolen] -= 1
            player.resources[stolen] += 1
            if player.is_human:
                rc = RESOURCE_COLOR[stolen]
                show_message(f"從 {player_colored(target.name, target)} 偷到 {rc}{RESOURCE_ZH[stolen]}{C.RESET}！")
            else:
                show_ai_action(player, f"從 {target.name} 偷取 1 張資源")

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build_road(self, player, edge):
        """Build a road."""
        player.spend_resources(COSTS['road'])
        self.board.place_road(edge, player.index)
        player.roads_left -= 1

        v1, v2 = tuple(EDGES[edge])
        if player.is_human:
            show_message(f"建造道路 {v1}↔{v2}")
        else:
            show_ai_action(player, f"建造道路 {v1}↔{v2}")

        self._update_longest_road()

    def build_settlement(self, player, vertex):
        """Build a settlement."""
        player.spend_resources(COSTS['settlement'])
        self.board.place_settlement(vertex, player.index)
        player.settlements_left -= 1

        if player.is_human:
            show_message(f"建造聚落於節點{vertex}")
        else:
            show_ai_action(player, f"建造聚落於節點{vertex}")

    def build_city(self, player, vertex):
        """Upgrade settlement to city."""
        player.spend_resources(COSTS['city'])
        self.board.place_city(vertex, player.index)
        player.cities_left -= 1
        player.settlements_left += 1  # Settlement piece returns

        if player.is_human:
            show_message(f"升級城市於節點{vertex}")
        else:
            show_ai_action(player, f"升級城市於節點{vertex}")

    def buy_dev_card(self, player):
        """Buy a development card."""
        player.spend_resources(COSTS['dev_card'])
        card = self.dev_deck.draw()
        if card is None:
            show_message("發展卡已用完！")
            return

        if card == DevCardType.VICTORY_POINT:
            player.victory_point_cards += 1
            if player.is_human:
                show_message(f"獲得發展卡: {CARD_NAMES_ZH[card]}！（+1 隱藏勝利點數）")
            else:
                show_ai_action(player, "購買發展卡")
        else:
            player.new_dev_cards.append(card)
            if player.is_human:
                show_message(f"獲得發展卡: {CARD_NAMES_ZH[card]}")
            else:
                show_ai_action(player, "購買發展卡")

    # ------------------------------------------------------------------
    # Development cards
    # ------------------------------------------------------------------

    def play_dev_card(self, player, card_type):
        """Play a development card."""
        if card_type not in player.dev_cards:
            return
        player.dev_cards.remove(card_type)
        player.played_dev_card_this_turn = True

        card_name = CARD_NAMES_ZH[card_type]

        if card_type == DevCardType.KNIGHT:
            if player.is_human:
                show_message(f"使用 {card_name}！")
            else:
                show_ai_action(player, f"使用 {card_name}")
            player.knights_played += 1

            if player.is_human:
                self._human_move_robber(player)
            else:
                self._ai_move_robber(player)

            self._update_largest_army()

        elif card_type == DevCardType.ROAD_BUILDING:
            if player.is_human:
                show_message(f"使用 {card_name}！免費建造 2 條道路。")
                for i in range(2):
                    if player.roads_left <= 0:
                        break
                    valid = self.board.get_valid_road_edges(player.index)
                    if not valid:
                        break
                    edge_options = [(e, f"道路 {tuple(EDGES[e])}") for e in valid]
                    edge = prompt_choice(f"第 {i+1} 條道路:", edge_options)
                    if edge is not None:
                        self.board.place_road(edge, player.index)
                        player.roads_left -= 1
                self._update_longest_road()
            else:
                show_ai_action(player, f"使用 {card_name}")
                edges = ai_choose_road_building_edges(player, self.board)
                for e in edges:
                    v1, v2 = tuple(EDGES[e])
                    show_ai_action(player, f"  免費道路 {v1}↔{v2}")
                self._update_longest_road()

        elif card_type == DevCardType.YEAR_OF_PLENTY:
            if player.is_human:
                show_message(f"使用 {card_name}！從銀行拿取 2 張任意資源。")
                for i in range(2):
                    res_options = [(r, f"{RESOURCE_COLOR[r]}{RESOURCE_ZH[r]}{C.RESET}")
                                   for r in Resource]
                    res = prompt_choice(f"第 {i+1} 張資源:", res_options, allow_cancel=False)
                    if res is not None:
                        player.add_resource(res)
            else:
                show_ai_action(player, f"使用 {card_name}")
                r1, r2 = ai_choose_year_of_plenty(player)
                player.add_resource(r1)
                player.add_resource(r2)
                show_ai_action(player, f"  拿取 {RESOURCE_ZH[r1]} 和 {RESOURCE_ZH[r2]}")

        elif card_type == DevCardType.MONOPOLY:
            if player.is_human:
                show_message(f"使用 {card_name}！宣告一種資源，所有玩家必須交出該資源。")
                res_options = [(r, f"{RESOURCE_COLOR[r]}{RESOURCE_ZH[r]}{C.RESET}")
                               for r in Resource]
                res = prompt_choice("宣告哪種資源?", res_options, allow_cancel=False)
            else:
                res = ai_choose_monopoly_resource(player, self.players)
                show_ai_action(player, f"使用 {card_name}，宣告 {RESOURCE_ZH[res]}")

            if res is not None:
                total_stolen = 0
                for p in self.players:
                    if p.index != player.index:
                        amt = p.resources[res]
                        if amt > 0:
                            p.resources[res] = 0
                            player.resources[res] += amt
                            total_stolen += amt
                show_message(f"獲得 {total_stolen} 張 {RESOURCE_ZH[res]}！")

    # ------------------------------------------------------------------
    # Longest road / Largest army
    # ------------------------------------------------------------------

    def _update_longest_road(self):
        """Recalculate longest road award."""
        best_player = None
        best_length = 4  # Need at least 5

        for p in self.players:
            length = self.board.longest_road(p.index)
            if length > best_length:
                best_length = length
                best_player = p

        if best_player and best_player != self.longest_road_player:
            # Transfer longest road
            if self.longest_road_player:
                self.longest_road_player.has_longest_road = False
            best_player.has_longest_road = True
            self.longest_road_player = best_player
            show_message(colored(
                f"🛤 {player_colored(best_player.name, best_player)} "
                f"獲得最長道路！(長度:{best_length})", C.BOLD))

    def _update_largest_army(self):
        """Recalculate largest army award."""
        best_player = None
        best_knights = 2  # Need at least 3

        for p in self.players:
            if p.knights_played > best_knights:
                best_knights = p.knights_played
                best_player = p

        if best_player and best_player != self.largest_army_player:
            if self.largest_army_player:
                self.largest_army_player.has_largest_army = False
            best_player.has_largest_army = True
            self.largest_army_player = best_player
            show_message(colored(
                f"⚔ {player_colored(best_player.name, best_player)} "
                f"獲得最大騎士團！(騎士:{best_knights})", C.BOLD))

    # ------------------------------------------------------------------
    # Victory check
    # ------------------------------------------------------------------

    def _check_victory(self, player):
        """Check if a player has won (10+ VP)."""
        vp = player.victory_points()
        if vp >= 10:
            self.game_over = True
            self.winner = player
            return True
        return False
