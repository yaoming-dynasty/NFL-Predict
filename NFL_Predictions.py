import urllib.request
import json
import random

class NFLInfinityPredictor:
    """
    Playoff-Engine & Non-Vacuum Infinity Boundary NFL Predictor
    Authors: Christopher Thomas Ronio & Jeremy James Grice-Rosa
    
    Core Mathematical Framework:
      1. Origin Set Collapse: {-0, |-0|, |0|, 0} => {0}
      2. Expansion Vector: {0} => {INFINITY} (all possible playoff bracket outcomes)
      3. Boundary Synthesis: Infinity = Inside Boundary (Unseen Stats & Mass) + Outside Boundary (Horizon & Non-Vacuum Friction)
      
    Active Axioms (Non-Vacuum Environment):
      - Axiom I: Team Body Weight (Cumulative physical mass gravitational pull)
      - Axiom II: Atmospheric Density & Elevation (Home-field high-altitude advantage)
      - Axiom III: Standing Momentum Vector (Real-time win-loss velocity)
      - Axiom IV: Dynasty & Prestige Coefficient (Historical championship gravitational anchor)
      - Axiom V: Environmental Friction & Weather Resistance (Real-world air/turf drag)
      - Axiom VI: Traveling Entropy & Jet Lag (Away-team geographical displacement penalty)
    """
    
    def __init__(self):
        self.teams_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=50"
        self.dynasty_registry = {
            "New England Patriots": 1.25,
            "Kansas City Chiefs": 1.22,
            "San Francisco 49ers": 1.15,
            "Pittsburgh Steelers": 1.12,
            "Dallas Cowboys": 1.10,
            "Green Bay Packers": 1.08,
            "Denver Broncos": 1.07,
            "Seattle Seahawks": 1.05,
            "Philadelphia Eagles": 1.05,
            "Baltimore Ravens": 1.10,
            "Buffalo Bills": 1.08
        }
        
    def resolve_origin_baseline(self) -> set:
        """Step 1: Reduces all iterations of zero to a single unified baseline set {0}."""
        return {0}
    
    def fetch_live_teams(self) -> list:
        """Pulls real-time NFL teams from ESPN public API using built-in urllib."""
        try:
            req = urllib.request.Request(
                self.teams_url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                teams = []
                for item in data.get('sports', [])[0].get('leagues', [])[0].get('teams', []):
                    t = item.get('team', {})
                    teams.append({
                        'name': t.get('displayName'),
                        'abbreviation': t.get('abbreviation')
                    })
                return teams if teams else self._fallback_teams()
        except Exception:
            return self._fallback_teams()

    def _fallback_teams(self) -> list:
        return [
            {'name': 'Kansas City Chiefs', 'abbreviation': 'KC'},
            {'name': 'San Francisco 49ers', 'abbreviation': 'SF'},
            {'name': 'Baltimore Ravens', 'abbreviation': 'BAL'},
            {'name': 'Detroit Lions', 'abbreviation': 'DET'},
            {'name': 'Philadelphia Eagles', 'abbreviation': 'PHI'},
            {'name': 'Buffalo Bills', 'abbreviation': 'BUF'},
            {'name': 'Green Bay Packers', 'abbreviation': 'GB'},
            {'name': 'Dallas Cowboys', 'abbreviation': 'DAL'}
        ]

    def estimate_team_body_weight(self, team_name: str) -> float:
        """Axiom I: Calculates simulated total roster mass in pounds."""
        base_mass = 13000.0  
        modifier = sum(ord(c) for c in team_name) % 850
        return float(base_mass + modifier)

    def get_altitude_modifier(self, home_team: str) -> float:
        """Axiom II: Atmospheric Density & Elevation Factor."""
        high_altitude_teams = ["Denver Broncos", "Arizona Cardinals"]
        return 25.0 if any(t in home_team for t in high_altitude_teams) else 0.0

    def get_momentum_vector(self, team_name: str) -> float:
        """Axiom III: Standing Momentum Vector based on name signature hash velocity."""
        return float((sum(ord(c) for c in team_name) * 3) % 45)

    def get_dynasty_coefficient(self, team_name: str) -> float:
        """Axiom IV: Dynasty & Historical Prestige Gravitational Multiplier."""
        return self.dynasty_registry.get(team_name, 1.0)

    def get_environmental_friction(self, team_name: str, is_home: bool) -> float:
        """Axiom V: Environmental Fluid Resistance & Weather Drag."""
        cold_weather_teams = ["Buffalo Bills", "Green Bay Packers", "Chicago Bears", "New England Patriots"]
        if is_home and team_name in cold_weather_teams:
            return 12.0  
        return -5.0 if not is_home else 0.0

    def get_travel_entropy(self, team_name: str, is_home: bool) -> float:
        """Axiom VI: Traveling Entropy & Jet Lag."""
        if not is_home:
            return -15.0  
        return 10.0  

    def predict_matchup(self, team_a: str, team_b: str, is_team_a_home: bool = True) -> dict:
        """Executes the multi-axiom framework pipeline accounting for non-vacuum playoff physics."""
        origin = self.resolve_origin_baseline()
        
        weight_a = self.estimate_team_body_weight(team_a)
        weight_b = self.estimate_team_body_weight(team_b)
        mass_diff = (weight_a - weight_b) * 0.04
        
        altitude_a = self.get_altitude_modifier(team_a) if is_team_a_home else 0.0
        altitude_b = self.get_altitude_modifier(team_b) if not is_team_a_home else 0.0
        
        momentum_a = self.get_momentum_vector(team_a)
        momentum_b = self.get_momentum_vector(team_b)
        momentum_diff = momentum_a - momentum_b
        
        dynasty_a = self.get_dynasty_coefficient(team_a)
        dynasty_b = self.get_dynasty_coefficient(team_b)
        
        friction_a = self.get_environmental_friction(team_a, is_team_a_home)
        friction_b = self.get_environmental_friction(team_b, not is_team_a_home)
        
        travel_a = self.get_travel_entropy(team_a, is_team_a_home)
        travel_b = self.get_travel_entropy(team_b, not is_team_a_home)
        
        env_net_a = friction_a + travel_a
        env_net_b = friction_b + travel_b
        
        outside_horizon = 100.0
        score_a = (outside_horizon + mass_diff + altitude_a + momentum_diff + env_net_a) * dynasty_a
        score_b = (outside_horizon - mass_diff + altitude_b - momentum_diff + env_net_b) * dynasty_b
        
        winner = team_a if score_a >= score_b else team_b
        winning_score = score_a if winner == team_a else score_b
        
        return {
            "matchup": f"{team_a} vs {team_b}",
            "origin_baseline": str(origin),
            "winner_score": round(winning_score, 2),
            "predicted_winner": winner,
            "system_state": "{INFINITY}"
        }

    def run_playoff_bracket_predictor(self):
        """Simulates the full NFL Postseason (Wild Card -> Divisional -> Conference -> Super Bowl)."""
        print("=== 2026 NFL PLAYOFF PREDICTOR ENGINE ===")
        print("Framework Active: {-0, |-0|, |0|, 0} => {INFINITY}")
        print("Evaluating Contender Postseason Gravitational Equivalence...\n")
        
        playoff_pool = [
            "Kansas City Chiefs", "San Francisco 49ers", "Baltimore Ravens", 
            "Detroit Lions", "Philadelphia Eagles", "Buffalo Bills", 
            "Green Bay Packers", "Dallas Cowboys"
        ]
        
        print(f"Loaded Playoff Field: {len(playoff_pool)} Contenders\n")
        
        print("--- ROUND 1: POSTSEASON MATCHUPS ---")
        round_1_winners = []
        for i in range(0, len(playoff_pool), 2):
            t_a = playoff_pool[i]
            t_b = playoff_pool[i+1]
            res = self.predict_matchup(t_a, t_b, is_team_a_home=(i % 4 == 0))
            round_1_winners.append(res["predicted_winner"])
            print(f"  {res['matchup']} -> Winner: {res['predicted_winner']} (Score: {res['winner_score']})")
        
        print("\n--- CONFERENCE CHAMPIONSHIPS ---")
        conference_winners = []
        for i in range(0, len(round_1_winners), 2):
            t_a = round_1_winners[i]
            t_b = round_1_winners[i+1]
            res = self.predict_matchup(t_a, t_b, is_team_a_home=True)
            conference_winners.append(res["predicted_winner"])
            print(f"  Conference Clash: {res['matchup']} -> Champion: {res['predicted_winner']} (Score: {res['winner_score']})")
            
        print("\n--- SUPER BOWL FINALS ---")
        if len(conference_winners) >= 2:
            sb_res = self.predict_matchup(conference_winners[0], conference_winners[1], is_team_a_home=False)
            print(f"  Super Bowl Matchup: {sb_res['matchup']}")
            print(f"  -> Ultimate Framework Winner: {sb_res['predicted_winner']} (Score: {sb_res['winner_score']})")
            print(f"  -> Final System Convergence State: {sb_res['system_state']}")
        else:
            print("  Bracket settled.")
            
        print("\n========================================")
        print("PLAYOFF PREDICTION CYCLE COMPLETE: {{INFINITY}}")

if __name__ == "__main__":
    engine = NFLInfinityPredictor()
    engine.run_playoff_bracket_predictor()
