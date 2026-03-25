#!/usr/bin/env python3
"""Catan Terminal Game — 卡坦島終端版

A complete implementation of the Settlers of Catan board game
for the terminal. 1 human player vs 3 AI opponents.

Run: python3 main.py
"""

import sys
from display import C, colored, clear_screen
from game import Game


def show_welcome():
    clear_screen()
    print()
    print(colored("  ╔══════════════════════════════════════╗", C.BOLD + C.CYAN))
    print(colored("  ║                                      ║", C.BOLD + C.CYAN))
    print(colored("  ║     🏝  歡迎來到卡坦島！ 🏝          ║", C.BOLD + C.CYAN))
    print(colored("  ║     The Settlers of Catan            ║", C.BOLD + C.CYAN))
    print(colored("  ║                                      ║", C.BOLD + C.CYAN))
    print(colored("  ║     終端版 Terminal Edition           ║", C.BOLD + C.CYAN))
    print(colored("  ║                                      ║", C.BOLD + C.CYAN))
    print(colored("  ╚══════════════════════════════════════╝", C.BOLD + C.CYAN))
    print()
    print(f"  {C.BOLD}遊戲規則:{C.RESET}")
    print(f"  • 你（玩家）vs 3 個電腦對手")
    print(f"  • 建造聚落、城市和道路來擴展領土")
    print(f"  • 透過擲骰子獲取資源，與其他玩家交易")
    print(f"  • 第一個達到 {C.BOLD}10 勝利點數{C.RESET} 的玩家獲勝！")
    print()
    print(f"  {C.BOLD}資源:{C.RESET}")
    print(f"  • {C.BRICK_C}磚塊{C.RESET}(丘陵) {C.ORE_C}礦石{C.RESET}(山脈) "
          f"{C.WOOL_C}羊毛{C.RESET}(牧場) {C.GRAIN_C}麥子{C.RESET}(農田) "
          f"{C.LUMBER_C}木材{C.RESET}(森林)")
    print()
    print(f"  {C.BOLD}建築費用:{C.RESET}")
    print(f"  • 道路: 磚×1 木×1")
    print(f"  • 聚落: 磚×1 木×1 毛×1 麥×1 (1 VP)")
    print(f"  • 城市: 麥×2 礦×3 (2 VP)")
    print(f"  • 發展卡: 礦×1 毛×1 麥×1")
    print()


def main():
    num_ai = 3
    if len(sys.argv) > 1:
        try:
            num_ai = int(sys.argv[1])
            num_ai = max(1, min(5, num_ai))
        except ValueError:
            pass

    show_welcome()
    try:
        input(f"  {C.BOLD}按 Enter 開始遊戲...{C.RESET}")
    except (EOFError, KeyboardInterrupt):
        print("\n  再見！")
        return

    try:
        game = Game(num_ai=num_ai)
        game.play()
    except KeyboardInterrupt:
        print(f"\n\n  {C.BOLD}遊戲中斷。再見！{C.RESET}\n")
    except EOFError:
        print(f"\n\n  {C.BOLD}遊戲結束。再見！{C.RESET}\n")


if __name__ == '__main__':
    main()
