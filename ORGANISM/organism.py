import subprocess
import sys
import time

# --- Shared Governance Policy ---
MAX_VAL = 100
MIN_VAL = 0
DECAY_RATE = 2
AUTO_HEAL_RATE = 15
VENOM_DAMAGE = 20

def read_state():
    try:
        result = subprocess.run(['cat', 'state.txt'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def update_state(old_state_dict, new_state_dict):
    for key in new_state_dict:
        old_val = old_state_dict[key]
        new_val = new_state_dict[key]
        if old_val != new_val:
            sed_command = f's/{key}={old_val}/{key}={new_val}/g'
            subprocess.run(['sed', '-i', sed_command, 'state.txt'], check=True)

def parse_state(state_string):
    state_dict = {
        "MEMORY_IMPORTANCE": 0, "LOGIC_LEVEL": 0, "EMOTION_LEVEL": 0, 
        "HEALTH": 100, "VENOM_LEVEL": 0, "AGE": 0, "MAX_HEALTH": 100,
        "SYM_POWER": 0, "SYM_BOND": 0
    }
    if not state_string: return state_dict
    
    for line in state_string.split('\n'):
        if "=" in line:
            key, val = line.split("=")
            if key in state_dict:
                try:
                    state_dict[key] = int(val)
                except ValueError:
                    pass
    return state_dict

def agent_one_host(user_input, current_state):
    """AGENT 1: The Host Organism. Reacts to external user stimuli."""
    new_state = current_state.copy()
    user_input = user_input.lower()
    
    new_state["AGE"] += 1
    if new_state["AGE"] % 5 == 0:
        new_state["MAX_HEALTH"] -= 2
        
    logic_hits = sum(1 for word in ['code', 'system', 'calculate', 'why', 'how', 'logic', 'data'] if word in user_input)
    emotion_hits = sum(1 for word in ['happy', 'angry', 'sad', 'feel', 'good', 'bad', 'love', 'hate'] if word in user_input)
    venom_hits = sum(1 for word in ['poison', 'virus', 'kill', 'attack', 'venom', 'destroy'] if word in user_input)
    anti_venom_hits = sum(1 for word in ['cure', 'heal', 'antidote', 'anti-venom', 'repair'] if word in user_input)
    
    new_state["LOGIC_LEVEL"] += (logic_hits * 5) - DECAY_RATE
    new_state["EMOTION_LEVEL"] += (emotion_hits * 5) - DECAY_RATE
    new_state["MEMORY_IMPORTANCE"] += len(user_input.split()) - DECAY_RATE
    
    if venom_hits > 0:
        new_state["VENOM_LEVEL"] += (venom_hits * 25)
    if anti_venom_hits > 0:
        new_state["VENOM_LEVEL"] = 0 
        
    if new_state["VENOM_LEVEL"] > 0:
        new_state["HEALTH"] -= VENOM_DAMAGE
    elif new_state["HEALTH"] < new_state["MAX_HEALTH"]:
        new_state["HEALTH"] += AUTO_HEAL_RATE
        
    return new_state

def agent_two_symbiote(current_state):
    """AGENT 2: The Symbiote. Reacts autonomously to the Host's state via the shared environment."""
    new_state = current_state.copy()
    action_taken = None
    
    # Symbiote feeds on high emotion
    if new_state["EMOTION_LEVEL"] > 60:
        new_state["SYM_POWER"] += 5
        new_state["SYM_BOND"] += 2
        action_taken = "Feeding on Host emotions."
        
    # Symbiote autonomous protection protocol
    if new_state["VENOM_LEVEL"] > 0 and new_state["SYM_POWER"] >= 10:
        new_state["VENOM_LEVEL"] = 0
        new_state["SYM_POWER"] -= 10
        new_state["MAX_HEALTH"] -= 5 # The toll it takes on the host's body
        action_taken = "Autonomously purged venom. Host MAX_HEALTH degraded."

    # Symbiote overgrowth penalty
    if new_state["SYM_POWER"] > 80:
        new_state["HEALTH"] -= 10
        action_taken = "Symbiote overgrowth is draining Host vitality."

    return new_state, action_taken

def enforce_governance(state):
    for key in ["LOGIC_LEVEL", "EMOTION_LEVEL", "MEMORY_IMPORTANCE", "SYM_POWER", "SYM_BOND"]:
        if state[key] > MAX_VAL: state[key] = MAX_VAL
        elif state[key] < MIN_VAL: state[key] = MIN_VAL
            
    if state["HEALTH"] > state["MAX_HEALTH"]: state["HEALTH"] = state["MAX_HEALTH"]
    if state["HEALTH"] < MIN_VAL: state["HEALTH"] = MIN_VAL
    if state["MAX_HEALTH"] < MIN_VAL: state["MAX_HEALTH"] = MIN_VAL
    return state

def run_multi_agent_system():
    print("--- Multi-Agent Ecosystem v5.0: Host & Symbiote Active ---")
    print("Commands: logical/emotional words, 'attack', 'cure'. Type 'exit' to leave.\n")
    
    while True:
        try:
            user_input = input("ecosystem-term> ").strip()
            if user_input.lower() == 'exit': sys.exit(0)
            if not user_input: continue

            # --- SENSE ---
            env_state_str = read_state()
            env_state = parse_state(env_state_str)
            
            # --- AGENT 1 (HOST) EXECUTES ---
            host_state = agent_one_host(user_input, env_state)
            host_state = enforce_governance(host_state)
            update_state(env_state, host_state) # Writes to environment
            
            # --- AGENT 2 (SYMBIOTE) EXECUTES ---
            # It reads the newly updated environment left by the Host
            updated_env_str = read_state()
            updated_env = parse_state(updated_env_str)
            
            symbiote_state, sym_action = agent_two_symbiote(updated_env)
            symbiote_state = enforce_governance(symbiote_state)
            update_state(updated_env, symbiote_state) # Writes to environment
            
            # --- FEEDBACK ---
            print("\n[SYSTEM METRICS]")
            for key in symbiote_state:
                diff = symbiote_state[key] - env_state[key]
                if diff != 0 or key in ["HEALTH", "MAX_HEALTH", "VENOM_LEVEL", "SYM_POWER"]:
                    shift = f"(+{diff})" if diff >= 0 else f"({diff})"
                    print(f" * {key}: {symbiote_state[key]} {shift}")
            
            print("\n--- AGENT RESPONSES ---")
            if symbiote_state["MAX_HEALTH"] <= 0 or symbiote_state["HEALTH"] <= 0:
                print("[HOST CRITICAL] The Host organism has died.")
                sys.exit(0)
                
            print(f"[HOST]: Processing cycle {symbiote_state['AGE']} complete.")
            
            if sym_action:
                print(f"[SYMBIOTE]: {sym_action}")
            else:
                print("[SYMBIOTE]: Dormant.")
            print("-------------------------\n")
            
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    run_multi_agent_system()
