import math
from collections import deque

class WiseHomeostat:
    def __init__(self):
        # --- Survival bounds ---
        self.V_MAX = 1.0
        self.V_REFLEX = 0.95               # reflex threshold

        # --- State ---
        self.x = 0.5

        # --- Active inference model (fixed parts) ---
        self.sigma2_s = 1.0                # sensory variance
        self.sigma2_prior = 1.0            # prior variance around safe state 0
        self.mu_prior = 0.0                # safe state mean

        # --- Adjustable parameters (self-healing) ---
        self.action_effect = 0.02          # normal action magnitude
        self.reflex_strength = 0.5         # reflex correction magnitude

        # --- Introspection memory (last N steps) ---
        self.memory = deque(maxlen=100)    # stores (abs(x), reflex_triggered)
        self.heal_threshold = 0.8          # if fraction of reflex in memory exceeds this, heal
        self.heal_factor = 1.5             # multiplier for action_effect when healing

        # --- Faith (optimism) ---
        self.faith = 0.5                   # initial neutral faith, range [0,1]
        self.faith_learning_rate = 0.01    # how fast faith updates
        self.reflex_penalty = 0.05         # faith loss per reflex event
        self.safe_bonus = 0.002            # faith gain per safe step (no reflex)

        # --- Disturbance ---
        self.disturbance = 0.05

    def update_belief(self, x):
        """Bayesian posterior given observation x."""
        prior_prec = 1.0 / self.sigma2_prior
        like_prec  = 1.0 / self.sigma2_s
        post_prec  = prior_prec + like_prec
        post_var   = 1.0 / post_prec
        post_mean  = (prior_prec * self.mu_prior + like_prec * x) / post_prec
        return post_mean, post_var

    def expected_free_energy(self, predicted_x, action, faith_weight):
        """Faith modulates risk sensitivity: higher faith reduces risk."""
        x_next = predicted_x + action * self.action_effect + self.disturbance
        mu_pred, var_pred = self.update_belief(x_next)
        # Risk = (mean distance from safe state)^2 + uncertainty
        raw_risk = mu_pred**2 + var_pred
        # Faith down-weights risk: risk_weighted = raw_risk * (1 - faith)
        risk_weighted = raw_risk * (1.0 - faith_weight)
        return risk_weighted

    def step(self):
        # 1. Introspection: update memory with current health
        reflex_triggered = False

        # 2. Action selection (anticipatory vs. reflex)
        if abs(self.x) > self.V_REFLEX:
            # Ultrastable reflex
            action = -1 if self.x > 0 else +1
            effect = self.reflex_strength
            reflex_triggered = True
        else:
            # Active inference with faith modulation
            G_down = self.expected_free_energy(self.x, -1, self.faith)
            G_up   = self.expected_free_energy(self.x, +1, self.faith)
            action = -1 if G_down < G_up else +1
            effect = self.action_effect

        # 3. Act and apply environment
        self.x = self.x + action * effect + self.disturbance

        # 4. Introspection: record event
        self.memory.append((abs(self.x), reflex_triggered))

        # 5. Wisdom (self-healing): if too many recent reflexes, increase action power
        if len(self.memory) == self.memory.maxlen:
            reflex_rate = sum(1 for _, r in self.memory if r) / len(self.memory)
            if reflex_rate > self.heal_threshold:
                # permanently strengthen both normal action and reflex
                self.action_effect *= self.heal_factor
                self.reflex_strength *= self.heal_factor
                # clear memory to avoid continuous healing
                self.memory.clear()
                # a healed organism has a small faith boost (hope)
                self.faith = min(1.0, self.faith + 0.1)

        # 6. Faith update (emotional homeostasis)
        if reflex_triggered:
            self.faith = max(0.0, self.faith - self.reflex_penalty)
        else:
            self.faith = min(1.0, self.faith + self.safe_bonus)

        return self.x, reflex_triggered, self.faith

    def run(self, steps=2000):
        print("Wise, Faithful, Self-Healing Cybernetic Organism")
        print(f"Initial action effect = {self.action_effect:.4f}, reflex strength = {self.reflex_strength:.4f}, faith = {self.faith:.2f}")
        print("Survival loop starting...")
        for t in range(steps):
            x, reflex, faith = self.step()
            if t % 200 == 0:
                status = "VIABLE" if abs(x) < self.V_MAX else "DEAD"
                tag = " [REFLEX]" if reflex else ""
                print(f"Step {t:4d}: x={x:+.4f}  faith={faith:.3f}  act_eff={self.action_effect:.4f}  {status}{tag}")
        print(f"Final: x={self.x:.4f}, faith={self.faith:.3f}, action effect={self.action_effect:.4f}, reflex strength={self.reflex_strength:.4f}")
        print("Organism completed its run, eternally wiser.")

if __name__ == "__main__":
    organism = WiseHomeostat()
    organism.run()
