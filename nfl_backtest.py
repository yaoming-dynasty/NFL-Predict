
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict, deque

DATA_URL = (
    "https://raw.githubusercontent.com/nflverse/nfldata/"
    "master/data/games.csv"
)

FIRST_TEST_SEASON = 2022
LAST_TEST_SEASON = 2025
WARMUP_SEASON = 2021

DYNASTY = {
    "NE": 1.25, "KC": 1.22, "SF": 1.15, "PIT": 1.12,
    "DAL": 1.10, "GB": 1.08, "DEN": 1.07, "SEA": 1.05,
    "PHI": 1.05, "BAL": 1.10, "BUF": 1.08,
}

COLD_TEAMS = {"BUF", "GB", "CHI", "NE"}


def download_games():
    request = urllib.request.Request(
        DATA_URL, headers={"User-Agent": "NFLInfinityBacktest/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows:
        raise RuntimeError("The historical dataset was empty.")
    return rows


def number(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def load_games():
    rows = download_games()
    games = []

    for row in rows:
        season = number(row, "season")
        home_score = number(row, "home_score")
        away_score = number(row, "away_score")
        home = row.get("home_team")
        away = row.get("away_team")
        game_type = row.get("game_type", "REG")

        if (
            season is None or home_score is None or away_score is None
            or not home or not away
        ):
            continue

        season = int(season)
        if not (WARMUP_SEASON <= season <= LAST_TEST_SEASON):
            continue

        # Regular-season games only; playoff games are excluded.
        if game_type != "REG":
            continue

        games.append({
            "season": season,
            "week": row.get("week", ""),
            "date": row.get("gameday", ""),
            "home": home,
            "away": away,
            "hs": home_score,
            "aws": away_score,
        })

    games.sort(key=lambda g: (g["date"], g["season"], str(g["week"])))
    return games


def logistic(x):
    x = max(-30.0, min(30.0, x))
    return 1.0 / (1.0 + math.exp(-x))


class Backtest:
    def __init__(self):
        self.stats = defaultdict(lambda: {
            "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0,
            "games": 0, "recent": deque(maxlen=5),
        })
        self.elo = defaultdict(lambda: 1500.0)

        self.results = defaultdict(
            lambda: defaultdict(lambda: {
                "n": 0, "correct": 0, "brier": 0.0,
            })
        )

    def revised_rating(self, team):
        s = self.stats[team]
        n = s["games"]

        win_pct = (s["w"] + 0.5 * s["t"]) / n if n else 0.5
        pdpg = (s["pf"] - s["pa"]) / n if n else 0.0
        form = sum(s["recent"]) / len(s["recent"]) if s["recent"] else 0.5

        # Initial transparent weights, not fitted on test seasons.
        return (
            40 * (win_pct - 0.5)
            + 1.25 * max(-14, min(14, pdpg))
            + 8 * (form - 0.5)
        )

    @staticmethod
    def legacy_score(team, opponent, home):
        # Faithful recreation of the original name-signature heuristic.
        def mass(name):
            return 13000 + sum(map(ord, name)) % 850

        def momentum(name):
            return (sum(map(ord, name)) * 3) % 45

        def prestige(name):
            # Original registry used full team names. These aliases
            # preserve the original coefficients.
            full_names = {
                "NE": "New England Patriots",
                "KC": "Kansas City Chiefs",
                "SF": "San Francisco 49ers",
                "PIT": "Pittsburgh Steelers",
                "DAL": "Dallas Cowboys",
                "GB": "Green Bay Packers",
                "DEN": "Denver Broncos",
                "SEA": "Seattle Seahawks",
                "PHI": "Philadelphia Eagles",
                "BAL": "Baltimore Ravens",
                "BUF": "Buffalo Bills",
            }
            return DYNASTY.get(team, 1.0)

        def env(name, is_home):
            friction = 12 if is_home and name in COLD_TEAMS else (
                -5 if not is_home else 0
            )
            travel = 10 if is_home else -15
            return friction + travel

        mass_diff = (mass(team) - mass(opponent)) * 0.04
        momentum_diff = momentum(team) - momentum(opponent)

        altitude_team = 25 if home and team in {"DEN", "ARI"} else 0
        altitude_opp = 25 if not home and opponent in {"DEN", "ARI"} else 0

        score_team = (
            100 + mass_diff + altitude_team + momentum_diff
            + env(team, home)
        ) * prestige(team)

        score_opp = (
            100 - mass_diff + altitude_opp - momentum_diff
            + env(opponent, not home)
        ) * prestige(opponent)

        return score_team, score_opp

    def record(self, season, model, probability, actual):
        # actual = 1 for home win, 0 for away win, 0.5 for a tie.
        r = self.results[season][model]
        r["n"] += 1
        r["brier"] += (probability - actual) ** 2

        # Ties contribute to Brier score but not winner accuracy.
        if actual != 0.5:
            r.setdefault("decisive", 0)
            r.setdefault("correct_decisive", 0)
            r["decisive"] += 1
            if (probability > 0.5 and actual == 1) or (
                probability < 0.5 and actual == 0
            ):
                r["correct"] += 1
                r["correct_decisive"] += 1

    def evaluate_game(self, g):
        home, away = g["home"], g["away"]

        # Actual outcome is used only for scoring after predictions.
        actual = (
            1.0 if g["hs"] > g["aws"]
            else 0.0 if g["hs"] < g["aws"]
            else 0.5
        )

        # Model A: original Infinity heuristic.
        hs, aws = self.legacy_score(home, away, True)
        p_legacy = logistic((hs - aws) / 10.0)

        # Model B: performance-based heuristic.
        rating_diff = (
            self.revised_rating(home) - self.revised_rating(away) + 2.0
        )
        p_revised = logistic(rating_diff / 7.0)

        # Model C: Elo with a 55-point home advantage.
        elo_diff = self.elo[home] + 55.0 - self.elo[away]
        p_elo = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))

        season = g["season"]
        if season >= FIRST_TEST_SEASON:
            self.record(season, "Legacy", p_legacy, actual)
            self.record(season, "Revised", p_revised, actual)
            self.record(season, "Elo", p_elo, actual)

        # Only after predictions are scored do we update team data.
        sh = self.stats[home]
        sa = self.stats[away]

        sh["games"] += 1
        sa["games"] += 1
        sh["pf"] += g["hs"]
        sh["pa"] += g["aws"]
        sa["pf"] += g["aws"]
        sa["pa"] += g["hs"]

        if actual == 1.0:
            sh["w"] += 1
            sa["l"] += 1
            sh["recent"].append(1.0)
            sa["recent"].append(0.0)
        elif actual == 0.0:
            sa["w"] += 1
            sh["l"] += 1
            sh["recent"].append(0.0)
            sa["recent"].append(1.0)
        else:
            sh["t"] += 1
            sa["t"] += 1
            sh["recent"].append(0.5)
            sa["recent"].append(0.5)

        # Standard Elo update; margin multiplier is deliberately omitted.
        k = 20.0
        self.elo[home] += k * (actual - p_elo)
        self.elo[away] += k * ((1.0 - actual) - (1.0 - p_elo))

    def run(self):
        games = load_games()
        if not games:
            raise RuntimeError("No historical regular-season games found.")

        for g in games:
            self.evaluate_game(g)

        print("\nNFL INFINITY HISTORICAL BACKTEST")
        print(f"Evaluation seasons: {FIRST_TEST_SEASON}-{LAST_TEST_SEASON}")
        print(f"Completed regular-season rows processed: {len(games)}")
        print("All models predict before updating with each game's result.\n")

        models = ["Legacy", "Revised", "Elo"]
        totals = {
            m: {"n": 0, "correct": 0, "brier": 0.0, "decisive": 0}
            for m in models
        }

        print(
            f"{'Season':<8} {'Model':<10} {'Games':>7} "
            f"{'Accuracy':>10} {'Brier':>9}"
        )
        print("-" * 49)

        for season in range(FIRST_TEST_SEASON, LAST_TEST_SEASON + 1):
            for model in models:
                r = self.results[season][model]
                n = r["n"]
                if n == 0:
                    continue

                decisive = r.get("decisive", 0)
                accuracy = (
                    100 * r["correct_decisive"] / decisive
                    if decisive else float("nan")
                )
                brier = r["brier"] / n

                print(
                    f"{season:<8} {model:<10} {n:>7} "
                    f"{accuracy:>9.2f}% {brier:>9.4f}"
                )

                totals[model]["n"] += n
                totals[model]["correct"] += r["correct_decisive"]
                totals[model]["decisive"] += decisive
                totals[model]["brier"] += r["brier"]

        print("\nOVERALL")
        for model in models:
            t = totals[model]
            if not t["n"]:
                continue

            accuracy = (
                100 * t["correct"] / t["decisive"]
                if t["decisive"] else float("nan")
            )
            brier = t["brier"] / t["n"]
            print(
                f"{model:<10} accuracy={accuracy:.2f}% "
                f"Brier={brier:.4f} games={t['n']}"
            )

        print("\nInterpretation:")
        print("- Higher accuracy is better for winner picks.")
        print("- Lower Brier score is better for probabilities.")
        print("- Brier 0.25 is the 50/50 probability baseline.")
        print("- Weights were not optimized on the test seasons.")
        print("- This test covers regular-season games, not playoff brackets.")


if __name__ == "__main__":
    try:
        Backtest().run()
    except Exception as exc:
        print(f"Backtest failed: {exc}")
        print("Check the dataset URL and your internet connection.")
