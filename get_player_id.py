import http.client
import json

API_KEY = "962b90a9a72101644cb5889cd02a434b"

def get_player_id(name: str):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {"x-apisports-key": API_KEY}

    conn.request("GET", f"/players/profiles?search={name}", headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))

    players = data.get("response", [])

    if not players:
        print(f"No players found for '{name}'")
        return

    for entry in players:
        player = entry.get("player", {})
        player_id = player.get("id")
        first = player.get("firstname", "")
        last = player.get("lastname", "")
        print(f"ID: {player_id}  Name: {first} {last}")

if __name__ == "__main__":
    search_name = input("Enter player name to search: ")
    get_player_id(search_name)
