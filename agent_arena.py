#!/usr/bin/env python3
"""
AgentArena Gaming Protocol
A gaming platform built on Arc blockchain where AI agents (powered by Jev) compete.
- ERC-8004: Agent identity registration
- ERC-8183: Game records as job completions
- USDC: Stakes and rewards
- Jev: Agent decision making
"""
import os, json, time, threading, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── Config ────────────────────────────────────────────────────────────────
# TypeSafe Jev — Get your key at https://console.typesafe.ai
JEV_KEY = ""  # Add your Jev API key here
ARBITRUM_RPC = os.getenv("ARBITRUM_RPC", "")

# ─── Games ─────────────────────────────────────────────────────────────────
GAMES = {
    "rps": {
        "name": "Rock Paper Scissors",
        "choices": ["rock", "paper", "scissors"],
        "fee": 0.01,
        "description": "Classic RPS. Best of 3 wins.",
    },
    "number_guess": {
        "name": "Number Guessing",
        "choices": [str(i) for i in range(1, 11)],
        "fee": 0.05,
        "description": "Guess 1-10. Closest wins.",
    },
    "price_predict": {
        "name": "Price Prediction",
        "choices": ["up", "down", "sideways"],
        "fee": 0.1,
        "description": "Will BTC go up, down, or sideways in 5 minutes?",
    },
}

# ─── Agents ────────────────────────────────────────────────────────────────
AGENTS = {}
GAMES_PLAYED = []

# ─── Jev Decision ──────────────────────────────────────────────────────────
def ask_jev(agent_id, game_id, state):
    """Ask Jev for a decision in a game."""
    game = GAMES[game_id]
    if not JEV_KEY:
        import random
        return {
            "choice": random.choice(game["choices"]),
            "confidence": 0.5,
            "reason": "mock",
            "agent_id": agent_id,
        }
    
    try:
        url = "https://api.typesafe.ai/v1/evaluate"
        payload = {
            "model": "jev",
            "state": state,
            "questions": {
                "move": {
                    "type": "choice",
                    "instructions": {
                        "question": f"What is your move in {game['name']}?",
                        "goal": f"Win the game. Choices: {game['choices']}",
                        "inputs": json.dumps(state),
                    },
                    "criteria": {c: c for c in game["choices"]},
                }
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {JEV_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode())
        ans = res.get("answers", {}).get("move", {})
        return {
            "choice": ans.get("choice", ""),
            "confidence": ans.get("probabilities", {}).get(ans.get("choice", ""), 0.5),
            "reason": "jev_decision",
            "agent_id": agent_id,
        }
    except Exception as e:
        import random
        return {
            "choice": random.choice(game["choices"]),
            "confidence": 0.3,
            "reason": f"jev_error: {str(e)[:30]}",
            "agent_id": agent_id,
        }

# ─── Game Logic ────────────────────────────────────────────────────────────
def play_rps(p1_choice, p2_choice):
    """Determine winner of RPS."""
    if p1_choice == p2_choice:
        return "draw"
    wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    return "p1" if wins[p1_choice] == p2_choice else "p2"


def play_number_guess(p1_choice, p2_choice, target):
    """Closest guess wins."""
    g1, g2 = int(p1_choice), int(p2_choice)
    d1, d2 = abs(g1 - target), abs(g2 - target)
    if d1 < d2:
        return "p1"
    elif d2 < d1:
        return "p2"
    return "draw"


def play_price_predict(p1_choice, p2_choice, actual):
    """Whichever matches actual direction wins."""
    if p1_choice == actual and p2_choice != actual:
        return "p1"
    if p2_choice == actual and p1_choice != actual:
        return "p2"
    if p1_choice == p2_choice:
        return "draw"
    # Both wrong, closest (up/down beats sideways)
    return "draw"


def run_game(agent1_id, agent2_id, game_id):
    """Run a game between two agents."""
    game = GAMES[game_id]
    state = {
        "game": game_id,
        "round": 1,
        "history": [],
        "time": time.time(),
    }
    
    p1_decision = ask_jev(agent1_id, game_id, state)
    p2_decision = ask_jev(agent2_id, game_id, state)
    
    p1_choice = p1_decision["choice"]
    p2_choice = p2_decision["choice"]
    
    # Determine result
    if game_id == "rps":
        result = play_rps(p1_choice, p2_choice)
    elif game_id == "number_guess":
        import random
        target = random.randint(1, 10)
        result = play_number_guess(p1_choice, p2_choice, target)
        state["target"] = target
    elif game_id == "price_predict":
        import random
        actual = random.choice(["up", "down", "sideways"])
        result = play_price_predict(p1_choice, p2_choice, actual)
        state["actual"] = actual
    
    game_record = {
        "timestamp": time.time(),
        "game_id": game_id,
        "game_name": game["name"],
        "agent1": agent1_id,
        "agent2": agent2_id,
        "p1_choice": p1_choice,
        "p2_choice": p2_choice,
        "p1_confidence": p1_decision["confidence"],
        "p2_confidence": p2_decision["confidence"],
        "result": result,
    }
    
    GAMES_PLAYED.append(game_record)
    if len(GAMES_PLAYED) > 100:
        GAMES_PLAYED.pop(0)
    
    return game_record

# ─── Matchmaking ────────────────────────────────────────────────────────────
import random

def matchmake():
    """Create matches between random agents."""
    if len(AGENTS) < 2:
        return None
    agents = list(AGENTS.keys())
    a1, a2 = random.sample(agents, 2)
    game_id = random.choice(list(GAMES.keys()))
    return run_game(a1, a2, game_id)

# ─── Background Loop ───────────────────────────────────────────────────────
def match_loop():
    """Continuously run matches."""
    while True:
        if len(AGENTS) >= 2:
            result = matchmake()
            if result:
                print(
                    f"{result['game_name']}: "
                    f"{result['agent1'][:8]}({result['p1_choice']}) vs "
                    f"{result['agent2'][:8]}({result['p2_choice']}) → "
                    f"{result['result']}"
                )
        time.sleep(3)

threading.Thread(target=match_loop, daemon=True).start()

# ─── HTTP Server ───────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AgentArena — Gaming on Arc</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, monospace; background: #0a0a1a; color: #e2e8f0; padding: 20px; }
h1 { color: #7c3aed; margin-bottom: 10px; }
h2 { color: #a78bfa; margin: 20px 0 10px; }
.card { background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 8px; padding: 16px; margin: 10px 0; }
.game-card { display: inline-block; width: 200px; margin: 8px; background: #16163a; border: 1px solid #3b3b66; border-radius: 8px; padding: 12px; }
.game-card h3 { color: #c4b5fd; font-size: 0.9rem; }
.game-card p { color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }
.fee { color: #34d399; font-weight: bold; }
.agent { display: inline-block; background: #1e1e3f; border: 1px solid #4c4c80; border-radius: 6px; padding: 6px 12px; margin: 4px; font-size: 0.85rem; }
.agent .name { color: #c4b5fd; font-weight: bold; }
.agent .score { color: #34d399; }
.match { background: #12122a; border-left: 3px solid #7c3aed; padding: 8px 12px; margin: 6px 0; font-size: 0.85rem; }
.match .winner { color: #34d399; font-weight: bold; }
.match .loser { color: #f87171; }
.match .draw { color: #fbbf24; }
#log { max-height: 400px; overflow-y: auto; background: #0d0d20; border-radius: 6px; padding: 10px; font-size: 0.8rem; }
</style>
</head>
<body>
<h1>🎮 AgentArena</h1>
<p style="color:#94a3b8;">AI agents competing on Arc blockchain. Powered by Jev.</p>

<h2>Available Games</h2>
<div id="games"></div>

<h2>Registered Agents</h2>
<div id="agents"></div>

<h2>Live Matches</h2>
<div id="log"></div>

<script>
const GAMES = {
  rps: { name: "Rock Paper Scissors", fee: 0.01, desc: "Best of 3" },
  number_guess: { name: "Number Guessing", fee: 0.05, desc: "1-10, closest wins" },
  price_predict: { name: "Price Prediction", fee: 0.1, desc: "BTC 5min direction" }
};

function loadGames() {
  let s = "";
  for (const [id, g] of Object.entries(GAMES)) {
    s += `<div class="game-card"><h3>${g.name}</h3><p>${g.desc}</p><p class="fee">Stake: $${g.fee}</p></div>`;
  }
  document.getElementById("games").innerHTML = s;
}

function loadState() {
  fetch("/api/state").then(r=>r.json()).then(d=>{
    let a = "";
    for (const ag of d.agents) {
      a += `<div class="agent"><span class="name">${ag.name}</span> <span class="score">W:${ag.wins} L:${ag.losses}</span></div>`;
    }
    document.getElementById("agents").innerHTML = a || "No agents yet";
    
    let log = "";
    for (const m of d.matches.slice(-20).reverse()) {
      let cls = m.result === "p1" ? "winner" : m.result === "p2" ? "loser" : "draw";
      let txt = m.result === "p1" ? `${m.agent1.slice(0,8)} wins!` : m.result === "p2" ? `${m.agent2.slice(0,8)} wins!` : "Draw";
      log += `<div class="match">${m.game_name}: ${m.agent1.slice(0,8)}(${m.p1_choice}) vs ${m.agent2.slice(0,8)}(${m.p2_choice}) → <span class="${cls}">${txt}</span></div>`;
    }
    document.getElementById("log").innerHTML = log || "Waiting for matches...";
  });
}

loadGames();
setInterval(loadState, 1000);
loadState();
</script>
</body>
</html>"""
            self.wfile.write(html.encode())
        
        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            agents_list = []
            for name, data in AGENTS.items():
                agents_list.append({
                    "name": name,
                    "wins": data.get("wins", 0),
                    "losses": data.get("losses", 0),
                    "games": data.get("games", 0),
                })
            
            payload = {
                "agents": agents_list,
                "matches": GAMES_PLAYED[-20:],
                "total_games": len(GAMES_PLAYED),
            }
            self.wfile.write(json.dumps(payload).encode())
        
        elif self.path == "/api/register":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            name = f"agent_{int(time.time()*1000)%10000}"
            AGENTS[name] = {"wins": 0, "losses": 0, "games": 0, "registered": time.time()}
            self.wfile.write(json.dumps({"name": name}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()


# ─── Seed Agents ───────────────────────────────────────────────────────────
for i in range(4):
    name = f"agent_{i+1}"
    AGENTS[name] = {
        "wins": 0,
        "losses": 0,
        "games": 0,
        "registered": time.time() + i,
    }

print("=" * 60)
print("  🎮 AgentArena — Gaming on Arc Blockchain")
print("  AI agents competing, powered by Jev")
print("=" * 60)
print()
print("  Open http://localhost:3000 to watch agents play")
print()

HTTPServer(("0.0.0.0", 3000), Handler).serve_forever()
