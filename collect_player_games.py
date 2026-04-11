import http.client
import json
import csv
import time
import os

API_KEY = "962b90a9a72101644cb5889cd02a434b"
API_HOST = "v3.football.api-sports.io"


def api_get(path):
    conn = http.client.HTTPSConnection(API_HOST)
    headers = {"x-apisports-key": API_KEY}
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    return json.loads(res.read().decode("utf-8"))


def get_player_team(player_id, league_id, season):
    """Returns the team ID the player was on for the given league and season."""
    data = api_get(f"/players?id={player_id}&season={season}&league={league_id}")
    response = data.get("response", [])
    if not response:
        print(f"  No player data found for player {player_id} in league {league_id}, season {season}.")
        return None, None
    stats = response[0].get("statistics", [])
    if not stats:
        return None, None
    team = stats[0].get("team", {})
    return team.get("id"), team.get("name")


def get_fixtures(league_id, season, team_id):
    """Returns all finished fixtures for a team in a given league and season."""
    data = api_get(f"/fixtures?season={season}&league={league_id}&team={team_id}&status=FT")
    return data.get("response", [])


def get_player_fixture_stats(fixture_id, team_id, player_id):
    """Returns the stat block for a specific player in a specific fixture."""
    data = api_get(f"/fixtures/players?fixture={fixture_id}&team={team_id}")
    for team_block in data.get("response", []):
        for player_entry in team_block.get("players", []):
            if player_entry.get("player", {}).get("id") == player_id:
                stats_list = player_entry.get("statistics", [])
                return stats_list[0] if stats_list else None
    return None


def safe(d, *keys):
    """Safely traverse nested dict keys, returning None if any key is missing."""
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def collect_player_games(player_id, league_id, season):
    print(f"\nLooking up team for player {player_id} | league {league_id} | season {season}...")
    team_id, team_name = get_player_team(player_id, league_id, season)
    if not team_id:
        return []

    print(f"Team: {team_name} (ID: {team_id})")
    print("Fetching fixtures...")
    fixtures = get_fixtures(league_id, season, team_id)
    print(f"Found {len(fixtures)} finished fixtures. Pulling per-game stats...\n")

    games = []
    for i, fixture in enumerate(fixtures, 1):
        fixture_id  = fixture["fixture"]["id"]
        date        = fixture["fixture"]["date"][:10]
        home_team   = fixture["teams"]["home"]["name"]
        away_team   = fixture["teams"]["away"]["name"]
        home_goals  = fixture["goals"]["home"]
        away_goals  = fixture["goals"]["away"]

        # Throttle slightly to stay within rate limits
        time.sleep(0.25)

        stats = get_player_fixture_stats(fixture_id, team_id, player_id)
        if stats is None:
            # Player did not appear in this fixture
            continue

        minutes = safe(stats, "games", "minutes")
        if not minutes:
            # Player was listed but didn't play (e.g. unused sub)
            continue

        game = {
            "date":               date,
            "home_team":          home_team,
            "away_team":          away_team,
            "score":              f"{home_goals}-{away_goals}",
            "minutes_played":     minutes,
            "goals":              safe(stats, "goals", "total") or 0,
            "assists":            safe(stats, "goals", "assists") or 0,
            "shots_total":        safe(stats, "shots", "total") or 0,
            "shots_on_target":    safe(stats, "shots", "on") or 0,
            "passes_total":       safe(stats, "passes", "total") or 0,
            "passes_key":         safe(stats, "passes", "key") or 0,
            "pass_accuracy_pct":  safe(stats, "passes", "accuracy"),
            # free kicks: fouls drawn = free kicks won; fouls committed = free kicks conceded
            "free_kicks_won":     safe(stats, "fouls", "drawn") or 0,
            "fouls_committed":    safe(stats, "fouls", "committed") or 0,
            "dribbles_attempted": safe(stats, "dribbles", "attempts") or 0,
            "dribbles_success":   safe(stats, "dribbles", "success") or 0,
            "tackles":            safe(stats, "tackles", "total") or 0,
            "rating":             safe(stats, "games", "rating"),
        }

        games.append(game)
        print(
            f"  [{i:>2}] {date}  {home_team} vs {away_team}  {home_goals}-{away_goals}"
            f"  | {minutes}' | G:{game['goals']} A:{game['assists']}"
            f" | Shots:{game['shots_total']} | Passes:{game['passes_total']}"
            f" | FKW:{game['free_kicks_won']}"
        )

    return games


def save_to_csv(games, player_id, league_id, season):
    if not games:
        print("\nNo game data to save.")
        return
    os.makedirs("data", exist_ok=True)
    filename = os.path.join("data", f"player_{player_id}_league_{league_id}_season_{season}.csv")
    fieldnames = list(games[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(games)
    print(f"\nSaved {len(games)} games to {filename}")


if __name__ == "__main__":
    player_id = int(input("Enter player ID: "))
    league_id = int(input("Enter league ID: "))
    season    = int(input("Enter season year (e.g. 2022): "))

    games = collect_player_games(player_id, league_id, season)

    if games:
        print(f"\n=== {len(games)} games found ===")
        save_to_csv(games, player_id, league_id, season)
