"""Development cards for Catan."""

import random
from enum import Enum


class DevCardType(Enum):
    KNIGHT = "knight"
    VICTORY_POINT = "victory_point"
    ROAD_BUILDING = "road_building"
    YEAR_OF_PLENTY = "year_of_plenty"
    MONOPOLY = "monopoly"


CARD_NAMES_ZH = {
    DevCardType.KNIGHT: "騎士",
    DevCardType.VICTORY_POINT: "勝利點數",
    DevCardType.ROAD_BUILDING: "築路",
    DevCardType.YEAR_OF_PLENTY: "豐收年",
    DevCardType.MONOPOLY: "壟斷",
}

# Standard deck: 14 Knights, 5 VP, 2 Road Building, 2 Year of Plenty, 2 Monopoly
STANDARD_DECK = (
    [DevCardType.KNIGHT] * 14 +
    [DevCardType.VICTORY_POINT] * 5 +
    [DevCardType.ROAD_BUILDING] * 2 +
    [DevCardType.YEAR_OF_PLENTY] * 2 +
    [DevCardType.MONOPOLY] * 2
)


class DevCardDeck:
    """Manages the development card deck."""

    def __init__(self):
        self.cards = list(STANDARD_DECK)
        random.shuffle(self.cards)

    def draw(self):
        """Draw a card from the deck. Returns None if empty."""
        if self.cards:
            return self.cards.pop()
        return None

    def remaining(self):
        return len(self.cards)
