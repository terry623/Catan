"""Trading system for Catan."""

from board import Resource
from display import (
    prompt_choice, show_message, RESOURCE_ZH, RESOURCE_COLOR, C,
    player_colored, show_ai_action,
)


def get_trade_rate(player, board, resource):
    """Get the best trade rate for a player trading away a resource.

    Returns the number of that resource needed to get 1 of any other.
    """
    ports = board.get_player_ports(player.index)
    # Check for specific 2:1 port
    if resource in ports:
        return 2
    # Check for generic 3:1 port
    if None in ports:
        return 3
    return 4


def bank_trade(player, board):
    """Handle bank/port trading for a player.

    Returns True if a trade was made.
    """
    # Show available trades
    options = []
    for give_res in Resource:
        rate = get_trade_rate(player, board, give_res)
        if player.resources[give_res] >= rate:
            for get_res in Resource:
                if get_res != give_res:
                    rc_give = RESOURCE_COLOR[give_res]
                    rc_get = RESOURCE_COLOR[get_res]
                    text = (f"{rc_give}{rate} {RESOURCE_ZH[give_res]}{C.RESET}"
                            f" → {rc_get}1 {RESOURCE_ZH[get_res]}{C.RESET}")
                    options.append(((give_res, get_res, rate), text))

    if not options:
        show_message("你沒有足夠的資源進行銀行交易。")
        return False

    result = prompt_choice("選擇銀行交易:", options)
    if result is None:
        return False

    give_res, get_res, rate = result
    player.resources[give_res] -= rate
    player.resources[get_res] += 1
    rc_give = RESOURCE_COLOR[give_res]
    rc_get = RESOURCE_COLOR[get_res]
    show_message(f"交易完成: {rc_give}{rate} {RESOURCE_ZH[give_res]}{C.RESET}"
                 f" → {rc_get}1 {RESOURCE_ZH[get_res]}{C.RESET}")
    return True


def ai_bank_trade(player, board, needed_resources=None):
    """AI performs bank/port trades to get needed resources.

    Returns True if any trade was made.
    """
    if needed_resources is None:
        return False

    traded = False
    for need_res, need_amt in needed_resources.items():
        while player.resources[need_res] < need_amt:
            # Find a resource we can afford to trade away
            best_give = None
            best_rate = 99
            for give_res in Resource:
                if give_res == need_res:
                    continue
                rate = get_trade_rate(player, board, give_res)
                # Only trade if we have enough AND it's not a resource we also need
                surplus = player.resources[give_res] - needed_resources.get(give_res, 0)
                if surplus >= rate and rate < best_rate:
                    best_give = give_res
                    best_rate = rate

            if best_give is None:
                break

            player.resources[best_give] -= best_rate
            player.resources[need_res] += 1
            show_ai_action(player,
                f"銀行交易 {best_rate} {RESOURCE_ZH[best_give]} → 1 {RESOURCE_ZH[need_res]}")
            traded = True

    return traded


def ai_evaluate_trade(ai_player, give_res, give_amt, get_res, get_amt):
    """AI evaluates whether to accept a trade.

    Returns True if the trade is favorable.
    """
    # Simple valuation: accept if getting something we need
    # and giving something we have surplus of
    has_surplus = ai_player.resources[give_res] >= give_amt + 2
    needs_resource = ai_player.resources[get_res] < 2

    if needs_resource and has_surplus:
        return True
    # Accept even trades if we have excess
    if ai_player.resources[give_res] >= give_amt + 3:
        return True
    return False


def player_trade_with_ai(human, ai_players, board):
    """Human player initiates trade with AI players.

    Returns True if a trade was made.
    """
    # Choose what to give
    give_options = []
    for r in Resource:
        if human.resources[r] > 0:
            rc = RESOURCE_COLOR[r]
            give_options.append((r, f"{rc}{RESOURCE_ZH[r]}{C.RESET} (持有:{human.resources[r]})"))

    if not give_options:
        show_message("你沒有資源可以交易。")
        return False

    give_res = prompt_choice("你要提供什麼資源?", give_options)
    if give_res is None:
        return False

    # Choose amount to give
    max_give = human.resources[give_res]
    amt_options = [(i, str(i)) for i in range(1, max_give + 1)]
    give_amt = prompt_choice("要提供幾個?", amt_options)
    if give_amt is None:
        return False

    # Choose what to get
    get_options = []
    for r in Resource:
        if r != give_res:
            rc = RESOURCE_COLOR[r]
            get_options.append((r, f"{rc}{RESOURCE_ZH[r]}{C.RESET}"))
    get_res = prompt_choice("你想要什麼資源?", get_options)
    if get_res is None:
        return False

    get_amt_options = [(i, str(i)) for i in range(1, 5)]
    get_amt = prompt_choice("要幾個?", get_amt_options)
    if get_amt is None:
        return False

    # Ask each AI
    for ai in ai_players:
        if ai.resources[get_res] >= get_amt:
            accepts = ai_evaluate_trade(ai, get_res, get_amt, give_res, give_amt)
            if accepts:
                # Execute trade
                human.resources[give_res] -= give_amt
                human.resources[get_res] += get_amt
                ai.resources[get_res] -= get_amt
                ai.resources[give_res] += give_amt

                rc_g = RESOURCE_COLOR[give_res]
                rc_r = RESOURCE_COLOR[get_res]
                show_message(
                    f"{player_colored(ai.name, ai)} 接受了交易! "
                    f"{rc_g}{give_amt} {RESOURCE_ZH[give_res]}{C.RESET} ↔ "
                    f"{rc_r}{get_amt} {RESOURCE_ZH[get_res]}{C.RESET}")
                return True
            else:
                show_message(f"{player_colored(ai.name, ai)} 拒絕了交易。")

    show_message("沒有人接受這筆交易。")
    return False
