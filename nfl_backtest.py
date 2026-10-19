import csv
import datetime
import io
import json
import math
import os
import urllib.request
from collections import defaultdict, deque

DATA_URL = (
    "https://raw.githubusercontent.com/nflverse/nfldata/"
    "master/data/games.csv"
)
CACHE_FILE = "nfl_games_cache.csv"

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
    if os.path.exists(CACHE_FILE):
        print(f"Loading dataset from local cache ({CACHE_FILE})...")
        with open(CACHE_FILE, "r", encoding="utf-8-sig") as f:
            content = f.read()
    else:
        print("Downloading dataset from nflverse repository...")
        request = urllib.request.Request(
            DATA_URL, headers={"User-Agent": "NFLInfinityBacktest/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8-sig")
        with open(CACHE_FILE, "w", encoding="utf-8-sig") as f:
            f.write(content)

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
        gameday = row.get("gameday", "")

        if (
            season is None or home_score is None or away_score is None
            or not home or not away or not gameday
        ):
            continue

        season = int(season)
        if not (WARMUP_SEASON <= season <= LAST_TEST_SEASON):
            continue

        if game_type != "REG":
            continue

        try:
            game_date = datetime.date.fromisoformat(gameday)
        except ValueError:
            continue

        games.append({
            "season": season,
            "week": row.get("week", ""),
            "date": game_date,
            "home": home,
            "away": away,
            "hs": home_score,
            "aws": away_score,
        })

    # Sort strictly chronologically by date
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
        self.last_played = {}  # Tracks team date of last game for rest calculations

        self.results = defaultdict(
            lambda: defaultdict(lambda: {
                "n": 0, "correct": 0, "brier": 0.0,
            })
        )

    def revised_rating(self, team, rest_diff):
        s = self.stats[team]
        n = s["games"]

        win_pct = (s["w"] + 0.5 * s["t"]) / n if n else 0.5
        pdpg = (s["pf"] - s["pa"]) / n if n else 0.0
        form = sum(s["recent"]) / len(s["recent"]) if s["recent"] else 0.5

        # Grounded performance heuristic incorporating fatigue (rest_diff)
        return (
            40 * (win_pct - 0.5)
            + 1.25 * max(-14, min(14, pdpg))
            + 8 * (form - 0.5)
            + 1.5 * max(-3, min(3, rest_diff))
        )

    @staticmethod
    def legacy_score(team, opponent, home, rest_home, rest_away):
        def mass(name):
            return 13000 + sum(map(ord, name)) % 850

        def momentum(name):
            return (sum(map(ord, name)) * 3) % 45

        def prestige(name):
            return DYNASTY.get(name, 1.0)

        def env(name, is_home, rest_days):
            friction = 12 if is_home and name in COLD_TEAMS else (
                -5 if not is_home else 0
            )
            # Upgraded Axiom VI: Dynamic travel entropy offset by rest adjustment
            travel = (10 if is_home else -15) + (rest_days - 7) * 1.5
            return friction + travel

        mass_diff = (mass(team) - mass(opponent)) * 0.04
        momentum_diff = momentum(team) - momentum(opponent)

        altitude_team = 25 if home and team in {"DEN", "ARI"} else 0
        altitude_opp = 25 if not home and opponent in {"DEN", "ARI"} else 0

        score_team = (
            100 + mass_diff + altitude_team + momentum_diff
            + env(team, home, rest_home)
        ) * prestige(team)

        score_opp = (
            100 - mass_diff + altitude_opp - momentum_diff
            + env(opponent, not home, rest_away)
        ) * prestige(opponent)

        return score_team, score_opp

    def record(self, season, model, probability, actual):
        r = self.results[season][model]
        r["n"] += 1
        r["brier"] += (probability - actual) ** 2

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
        game_date = g["date"]

        # Calculate rest days since last game (default to 7 if opening week / unknown)
        rest_home = (game_date - self.last_played[home]).days if home in self.last_played else 7
        rest_away = (game_date - self.last_played[away]).days if away in self.last_played else 7
        rest_diff = rest_home - rest_away

        actual = (
            1.0 if g["hs"] > g["aws"]
            else 0.0 if g["hs"] < g["aws"]
            else 0.5
        )

        # Model A: Legacy Infinity Heuristic (with dynamic rest update)
        hs, aws = self.legacy_score(home, away, True, rest_home, rest_away)
        p_legacy = logistic((hs - aws) / 10.0)

        # Model B: Performance & Rest Heuristic
        rating_diff = (
            self.revised_rating(home, rest_diff) - self.revised_rating(away, -rest_diff) + 2.0
        )
        p_revised = logistic(rating_diff / 7.0)

        # Model C: Elo with home-field advantage & Rest differential adjustment
        elo_diff = self.elo[home] + 55.0 + (rest_diff * 4.0) - self.elo[away]
        p_elo = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))

        season = g["season"]
        if season >= FIRST_TEST_SEASON:
            self.record(season, "Legacy", p_legacy, actual)
            self.record(season, "Revised", p_revised, actual)
            self.record(season, "Elo", p_elo, actual)

        # Update last played date
        self.last_played[home] = game_date
        self.last_played[away] = game_date

        # Update team statistics trackers
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

        # Upgraded Elo with Margin-of-Victory (MOV) Multiplier
        point_diff = abs(g["hs"] - g["aws"])
        mov_multiplier = math.log(max(point_diff, 1) + 1.0) * (
            2.2 / (float(abs(self.elo[home] - self.elo[away])) * 0.001 + 2.2)
        )
        k = 20.0 * mov_multiplier
        
        self.elo[home] += k * (actual - p_elo)
        self.elo[away] += k * ((1.0 - actual) - (1.0 - p_elo))

    def run(self):
        games = load_games()
        if not games:
            raise RuntimeError("No historical regular-season games found.")

        for g in games:
            self.evaluate_game(g)

        print("\n=== NFL INFINITY ADVANCED BACKTEST ===")
        print(f"Evaluation seasons: {FIRST_TEST_SEASON}-{LAST_TEST_SEASON}")
        print(f"Total regular-season games processed: {len(games)}")
        print("Chronological validation complete with Rest Tracking & MOV Elo.\n")

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

        print("\n=== OVERALL PERFORMANCE ===")
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
        print("- Lower Brier score is better for calibrated probabilities.")
        print("- Brier 0.25 represents a random coin-flip baseline.")


if __name__ == "__main__":
    try:
        Backtest().run()
    except Exception as exc:
        print(f"Backtest failed: {exc}")
        print("Check your internet connection and permissions.")
