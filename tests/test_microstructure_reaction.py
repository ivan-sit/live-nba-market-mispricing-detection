from src.analysis.microstructure_reaction import Level, buy_yes_levels, roundtrip_profit, sell_yes_levels


def test_buy_and_sell_yes_levels_follow_kalshi_binary_book_semantics():
    book = {
        "yes_dollars": [["0.41", "10"], ["0.40", "5"]],
        "no_dollars": [["0.58", "7"], ["0.57", "3"]],
    }

    asks = buy_yes_levels(book)
    bids = sell_yes_levels(book)

    assert [(round(lvl.price, 2), lvl.size) for lvl in asks] == [(0.42, 7.0), (0.43, 3.0)]
    assert [(lvl.price, lvl.size) for lvl in bids] == [(0.41, 10.0), (0.4, 5.0)]


def test_roundtrip_profit_stops_when_marginal_edge_disappears():
    entry = [Level(0.40, 10), Level(0.42, 10), Level(0.45, 10)]
    exit_ = [Level(0.44, 12), Level(0.41, 20)]

    result = roundtrip_profit(entry, exit_)

    assert result["contracts"] == 12
    assert round(result["entry_cost"], 2) == 4.84
    assert round(result["exit_proceeds"], 2) == 5.28
    assert round(result["pnl"], 2) == 0.44
