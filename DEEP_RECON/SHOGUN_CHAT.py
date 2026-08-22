#!/usr/bin/env python3
import subprocess, json, time, re, os
from datetime import datetime

WALLET = "0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156"
LOG_FILE = "shogun_chat.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

def execute(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output}"

def heartbeat():
    engines = execute("ps aux | grep python | grep -v grep | wc -l").strip()
    proofs = execute("wc -l < MEGA.jsonl 2>/dev/null || echo 0").strip()
    last_vac = execute("tail -1 vacuum.log 2>/dev/null").strip() or "No vacuum data"
    last_mega = execute("tail -1 beacon_mega.log 2>/dev/null").strip() or "No MEGA data"
    return f"Engines: {engines}, Proofs: {proofs}\nLast VACUUM: {last_vac}\nLast MEGA: {last_mega}"

def parse_intent(user_input):
    inp = user_input.lower().strip()
    if any(word in inp for word in ["heartbeat","status","how are","pulse"]):
        return "heartbeat"
    elif any(word in inp for word in ["panic","kill all","emergency","stop everything"]):
        return "panic"
    elif any(word in inp for word in ["profit","how much","earnings","total"]):
        return "profit"
    elif any(word in inp for word in ["forge","create tool","generate script","make me a"]):
        return "forge"
    elif any(word in inp for word in ["backup","save vault"]):
        return "backup"
    elif any(word in inp for word in ["ghost","stealth","hide","decoy"]):
        return "ghost"
    elif any(word in inp for word in ["engine","start","stop","restart"]):
        return "engine"
    elif any(word in inp for word in ["list tools","what do you have","arsenal"]):
        return "tools"
    elif any(word in inp for word in ["help","what can you do"]):
        return "help"
    return None

def handle_intent(intent, raw):
    if intent == "heartbeat":
        return heartbeat()
    elif intent == "panic":
        out = execute("pkill -f python")
        return "All engines killed. Empire dormant."
    elif intent == "profit":
        last = execute("grep -o \"Total \\$[0-9.]*\" vacuum.log | tail -1").strip()
        return last if last else "No profit data yet."
    elif intent == "backup":
        out = execute("bash VAULT_BACKUP.sh")
        return out
    elif intent == "ghost":
        out = execute("bash STEALTH_MODE.sh")
        return out
    elif intent == "engine":
        if "start" in raw.lower():
            engines = ["BEACON","BEACON_MEGA","VACUUM","LIVE_VACUUM","KATANA","GOD_HAND"]
            for e in engines:
                execute(f"nohup python -u {e}.py > {e.lower()}.log 2>&1 &")
            return "All engines started."
        elif "stop" in raw.lower() or "kill" in raw.lower():
            execute("pkill -f python")
            return "All engines stopped."
        else:
            return "Say: start engines or stop engines"
    elif intent == "forge":
        name_match = re.search(r"named?\s+(\w+)", raw, re.I)
        action_match = re.search(r"that\s+(.*)", raw, re.I)
        if name_match and action_match:
            name = name_match.group(1)
            action = action_match.group(1).strip().replace("\"", "\\\"")
            cmd = f"python FORGE.py --name {name} --type sh --desc \"Chat generated\" --action \"{action}\""
            out = execute(cmd)
            return f"Tool forged: {out}"
        else:
            return "To forge a tool, say: forge a tool named [NAME] that [ACTION]. Example: forge a tool named HELLO that echo hello world"
    elif intent == "tools":
        files = execute("ls *.sh *.py 2>/dev/null | head -20")
        return f"Available tools:\n{files}"
    elif intent == "help":
        return """I understand:
- heartbeat / status
- panic / kill all
- profit
- backup
- ghost / stealth
- start engines / stop engines
- forge a tool named X that Y
- list tools
- help
Just talk to me."""
    else:
        return "I didn't understand. Type 'help' to see what I can do."

print("🤖 SHOGUN CHAT ACTIVE — talk to your empire")
print('Type "exit" to quit.')
while True:
    try:
        user = input("shogun> ")
        if user.lower().strip() == "exit":
            print("Stay sharp, Shogun.")
            break
        intent = parse_intent(user)
        if intent:
            response = handle_intent(intent, user)
            print(response)
            log(f"USER: {user} | INTENT: {intent} | RESPONSE: {response[:100]}")
        else:
            print("I didn't get that. Try 'help'.")
            log(f"USER: {user} | UNRECOGNIZED")
    except KeyboardInterrupt:
        print("\nUse 'exit' to quit.")
    except Exception as e:
        print(f"Chaos: {e}")
