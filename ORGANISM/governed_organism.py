#!/usr/bin/env python3
import argparse, hashlib, random

def run_organism(mode, emotion, seed, steps, outfile):
    rng = random.Random(seed)
    x, faith, action, reflex, gov_cooldown = 0.5, 0.0, 0.02, 0.5, 0
    alpha, beta, gamma, delta, dist_amp = 0.1, 0.05, 0.02, 0.01, 0.05

    for t in range(steps):
        disturbance = dist_amp * rng.uniform(-1,1)
        emotional_noise = 0.02 * faith * rng.uniform(-1,1) if emotion == "on" else 0.0
        if mode == "full":
            penalty = -0.1 * (action - 0.2) if action > 0.2 else 0.0
            if gov_cooldown > 0:
                gov_cooldown -= 1
                reflex = max(0.1, reflex - 0.005)
            else:
                reflex = min(5.0, reflex + delta * (0.5 - reflex))
        else:
            penalty = 0.0
            reflex = min(5.0, reflex + delta * (0.5 - reflex))
        error = 0.5 - x
        x += alpha * error + gamma * action + disturbance + emotional_noise + penalty
        faith += beta * (abs(error) - faith)
        faith = max(0.0, min(0.95, faith))
        action = min(0.2, 0.02 + 0.02 * abs(error))
        if t % 200 == 0:
            status = "VIABLE" if faith < 0.8 else "UNSTABLE"
            print(f"Step {t:4d}: x={x:+7.4f}  faith={faith:6.3f}  act={action:6.4f}  ref={reflex:5.3f}  {status}")

    final_state = {'x': round(x,6), 'faith': round(faith,6), 'action': round(action,6), 'reflex': round(reflex,6), 'mode': mode, 'emotion': emotion, 'seed': seed, 'steps': steps}
    state_str = str(final_state).encode()
    hash_digest = hashlib.sha256(state_str).hexdigest()
    with open(outfile, 'w') as f:
        f.write(f"Final state: {final_state}\nInvariant hash: {hash_digest}\n")
    print(f"\nFinal state: {final_state}\nInvariant hash: {hash_digest}\nOutput written to {outfile}")
    return final_state, hash_digest

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['vanilla','full'], default='vanilla')
    p.add_argument('--emotion', choices=['on','off'], default='off')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--steps', type=int, default=1000)
    p.add_argument('--out', default='output.txt')
    args = p.parse_args()
    run_organism(args.mode, args.emotion, args.seed, args.steps, args.out)

if __name__ == "__main__": main()
