import http.client
import json
import csv
import time
import os

API_KEY = "962b90a9a72101644cb5889cd02a434b"
API_HOST = "v3.football.api-sports.io"

WORLD_CUP_LEAGUE_ID = 1
SEASON = 2022


def api_get(path):
    conn = http.client.HTTPSConnection(API_HOST)
    headers = {"x-apisports-key": API_KEY}
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    return json.loads(res.read().decode("utf-8"))


def get_wc_teams():
    """Returns all teams that participated in the 2022 World Cup."""
    data = api_get(f"/teams?league={WORLD_CUP_LEAGUE_ID}&season={SEASON}")
    teams = []
    for entry in data.get("response", []):
        team = entry.get("team", {})
        teams.append({"id": team["id"], "name": team["name"]})
    return teams


def get_players_for_team(team_id):
    """
    Returns all players who appeared for a team in the 2022 World Cup.
    Handles pagination automatically.
    """
    players = []
    page = 1
    while True:
        data = api_get(
            f"/players?league={WORLD_CUP_LEAGUE_ID}&season={SEASON}"
            f"&team={team_id}&page={page}"
        )
        response = data.get("response", [])
        paging = data.get("paging", {})

        for entry in response:
            p = entry.get("player", {})
            players.append({
                "player_id":   p.get("id"),
                "name":        p.get("name"),
                "nationality": p.get("nationality"),
                "age":         p.get("age"),
                "position":    entry.get("statistics", [{}])[0]
                                   .get("games", {}).get("position"),
            })

        if paging.get("current", 1) >= paging.get("total", 1):
            break
        page += 1
        time.sleep(0.3)  # stay within rate limits between pages

    return players


def collect_world_cup_squads(output_path="roster_data/world_cup_2022_squads.csv"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("Fetching 2022 World Cup teams...")
    teams = get_wc_teams()
    print(f"Found {len(teams)} teams.\n")

    rows = []
    for team in teams:
        print(f"  Fetching squad for {team['name']} (ID: {team['id']})...")
        players = get_players_for_team(team["id"])
        print(f"    -> {len(players)} players found")

        for p in players:
            rows.append({
                "team_id":     team["id"],
                "team_name":   team["name"],
                "player_id":   p["player_id"],
                "player_name": p["name"],
                "nationality": p["nationality"],
                "age":         p["age"],
                "position":    p["position"],
            })

        time.sleep(0.5)  # throttle between teams

    fieldnames = [
        "team_id", "team_name", "player_id", "player_name",
        "nationality", "age", "position"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} player-team records saved to {output_path}")


if __name__ == "__main__":
    collect_world_cup_squads()
