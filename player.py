"""Player classes for Catan."""

from board import Resource

# Building costs
COSTS = {
    'road':       {Resource.BRICK: 1, Resource.LUMBER: 1},
    'settlement': {Resource.BRICK: 1, Resource.LUMBER: 1, Resource.WOOL: 1, Resource.GRAIN: 1},
    'city':       {Resource.GRAIN: 2, Resource.ORE: 3},
    'dev_card':   {Resource.ORE: 1, Resource.WOOL: 1, Resource.GRAIN: 1},
}

PLAYER_COLORS = ['red', 'blue', 'green', 'yellow']
PLAYER_NAMES_ZH = ['你', '電腦A', '電腦B', '電腦C']


class Player:
    """Base player class."""

    def __init__(self, index, name, color):
        self.index = index
        self.name = name
        self.color = color
        self.resources = {r: 0 for r in Resource}
        self.dev_cards = []          # list of DevCardType
        self.new_dev_cards = []      # bought this turn, can't play yet
        self.played_dev_card_this_turn = False
        self.knights_played = 0
        self.settlements_left = 5
        self.cities_left = 4
        self.roads_left = 15
        self.has_longest_road = False
        self.has_largest_army = False
        self.victory_point_cards = 0  # hidden VP from dev cards
        self.is_human = False

    def total_resources(self):
        return sum(self.resources.values())

    def has_resources(self, cost):
        """Check if player has enough resources for a cost dict."""
        return all(self.resources[r] >= amt for r, amt in cost.items())

    def spend_resources(self, cost):
        """Deduct resources for a cost dict."""
        for r, amt in cost.items():
            self.resources[r] -= amt

    def add_resource(self, resource, amount=1):
        if resource is not None:
            self.resources[resource] += amount

    def remove_resource(self, resource, amount=1):
        if resource is not None:
            self.resources[resource] = max(0, self.resources[resource] - amount)

    def can_build(self, building_type):
        """Check if player can afford and has pieces for a building type."""
        if building_type == 'road' and self.roads_left <= 0:
            return False
        if building_type == 'settlement' and self.settlements_left <= 0:
            return False
        if building_type == 'city' and self.cities_left <= 0:
            return False
        return self.has_resources(COSTS[building_type])

    def victory_points(self):
        """Calculate visible victory points."""
        vp = 0
        # Settlements and cities are tracked by the game
        # This is set externally
        vp += (5 - self.settlements_left)  # each settlement placed = 1 VP
        # Cities replace settlements, so: cities = (4 - cities_left)
        # Each city = 2 VP, but it replaced a settlement (which returned to pool)
        cities_built = 4 - self.cities_left
        vp += cities_built  # +1 extra VP per city (settlement already counted, city adds 1 more)
        if self.has_longest_road:
            vp += 2
        if self.has_largest_army:
            vp += 2
        vp += self.victory_point_cards
        return vp

    def end_turn_cards(self):
        """Move new dev cards to playable pool at end of turn."""
        self.dev_cards.extend(self.new_dev_cards)
        self.new_dev_cards = []
        self.played_dev_card_this_turn = False


class HumanPlayer(Player):
    def __init__(self, index):
        super().__init__(index, PLAYER_NAMES_ZH[index], PLAYER_COLORS[index])
        self.is_human = True


class AIPlayer(Player):
    def __init__(self, index):
        super().__init__(index, PLAYER_NAMES_ZH[index], PLAYER_COLORS[index])
        self.is_human = False
