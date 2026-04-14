import http.client
import json
import csv
import time
import os

API_KEY = "962b90a9a72101644cb5889cd02a434b"
API_HOST = "v3.football.api-sports.io"

WORLD_CUP_LEAGUE_ID = 1
SEASON = 2022
SQUADS_CSV = "roster_data/world_cup_2022_squads.csv"


def api_get(path):
    conn = http.client.HTTPSConnection(API_HOST)
    headers = {"x-apisports-key": API_KEY}
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    return json.loads(res.read().decode("utf-8"))


def safe(d, *keys):
    """Safely traverse nested dict keys, returning None if any key is missing."""
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def load_squad(team_query):
    """
    Reads the local squads CSV and finds the team whose name contains
    team_query (case-insensitive).  Returns (team_id, team_name, players_dict)
    where players_dict maps player_id -> {name, position}.
    """
    matches = {}  # team_name -> (team_id, players)

    with open(SQUADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tname = row["team_name"]
            if team_query.lower() in tname.lower():
                tid = int(row["team_id"])
                if tname not in matches:
                    matches[tname] = {"team_id": tid, "players": {}}
                pid = int(row["player_id"])
                matches[tname]["players"][pid] = {
                    "name":     row["player_name"],
                    "position": row["position"],
                }

    if not matches:
        return None, None, None

    if len(matches) > 1:
        print("Multiple teams matched your query:")
        for i, name in enumerate(matches, 1):
            print(f"  {i}. {name}")
        choice = int(input("Enter the number of the team you want: ")) - 1
        chosen = list(matches.keys())[choice]
    else:
        chosen = list(matches.keys())[0]

    entry = matches[chosen]
    return entry["team_id"], chosen, entry["players"]


def get_wc_fixtures(team_id):
    """Returns all finished World Cup 2022 fixtures for the given team."""
    data = api_get(
        f"/fixtures?league={WORLD_CUP_LEAGUE_ID}&season={SEASON}"
        f"&team={team_id}&status=FT"
    )
    fixtures = data.get("response", [])
    # Sort chronologically
    fixtures.sort(key=lambda f: f["fixture"]["date"])
    return fixtures


def get_fixture_player_stats(fixture_id, team_id):
    """
    Returns a dict mapping player_id -> stats block for every player
    in the team's entry for this fixture.
    """
    data = api_get(f"/fixtures/players?fixture={fixture_id}&team={team_id}")
    result = {}
    for team_block in data.get("response", []):
        if team_block.get("team", {}).get("id") != team_id:
            continue
        for entry in team_block.get("players", []):
            pid = safe(entry, "player", "id")
            stats_list = entry.get("statistics", [])
            if pid is not None and stats_list:
                result[pid] = stats_list[0]
    return result


def collect_team_wc_games(team_query):
    # ── 1. Resolve team from local CSV ──────────────────────────────────────
    team_id, team_name, players = load_squad(team_query)
    if team_id is None:
        print(f"No team found matching '{team_query}' in {SQUADS_CSV}.")
        print("Make sure you have already run get_world_cup_squads.py.")
        return

    print(f"\nTeam : {team_name}  (ID: {team_id})")
    print(f"Squad: {len(players)} players on roster\n")

    # ── 2. Fetch all WC fixtures for the team ───────────────────────────────
    print("Fetching World Cup fixtures...")
    fixtures = get_wc_fixtures(team_id)
    print(f"Found {len(fixtures)} finished matches.\n")

    if not fixtures:
        print("No finished fixtures found — nothing to save.")
        return

    # ── 3. Pull player stats for every fixture ──────────────────────────────
    rows = []

    for i, fixture in enumerate(fixtures, 1):
        fixture_id  = fixture["fixture"]["id"]
        date        = fixture["fixture"]["date"][:10]
        round_name  = safe(fixture, "league", "round") or ""
        home_team   = fixture["teams"]["home"]["name"]
        away_team   = fixture["teams"]["away"]["name"]
        home_goals  = fixture["goals"]["home"]
        away_goals  = fixture["goals"]["away"]
        score       = f"{home_goals}-{away_goals}"

        print(f"  [{i:>2}] {date}  {home_team} vs {away_team}  {score}  ({round_name})")

        time.sleep(0.3)
        fixture_stats = get_fixture_player_stats(fixture_id, team_id)

        for pid, pinfo in players.items():
            stats = fixture_stats.get(pid)
            if stats is None:
                continue  # player not in this fixture's data

            minutes = safe(stats, "games", "minutes")
            if not minutes:
                continue  # unused sub — no real appearance

            rows.append({
                "team_id":            team_id,
                "team_name":          team_name,
                "player_id":          pid,
                "player_name":        pinfo["name"],
                "position":           pinfo["position"],
                "fixture_id":         fixture_id,
                "date":               date,
                "round":              round_name,
                "home_team":          home_team,
                "away_team":          away_team,
                "score":              score,
                "minutes_played":     minutes,
                "rating":             safe(stats, "games", "rating"),
                "goals":              safe(stats, "goals", "total") or 0,
                "assists":            safe(stats, "goals", "assists") or 0,
                "shots_total":        safe(stats, "shots", "total") or 0,
                "shots_on_target":    safe(stats, "shots", "on") or 0,
                "passes_total":       safe(stats, "passes", "total") or 0,
                "passes_key":         safe(stats, "passes", "key") or 0,
                "pass_accuracy_pct":  safe(stats, "passes", "accuracy"),
                "free_kicks_won":     safe(stats, "fouls", "drawn") or 0,
                "fouls_committed":    safe(stats, "fouls", "committed") or 0,
                "dribbles_attempted": safe(stats, "dribbles", "attempts") or 0,
                "dribbles_success":   safe(stats, "dribbles", "success") or 0,
                "tackles":            safe(stats, "tackles", "total") or 0,
            })

    # ── 4. Save results ─────────────────────────────────────────────────────
    if not rows:
        print("\nNo player-game data found.")
        return

    os.makedirs("data", exist_ok=True)
    safe_name = team_name.lower().replace(" ", "_")
    output_path = os.path.join("data", f"wc2022_{safe_name}_all_games.csv")

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} player-game records saved to {output_path}")


if __name__ == "__main__":
    query = input("Enter team name or country (e.g. France, Brazil, England): ").strip()
    collect_team_wc_games(query)
