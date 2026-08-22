import math

class ImmortalHomeostat:
    def __init__(self):
        self.V_MAX = 1.0                      # viability bound
        self.V_REFLEX = 0.95                  # trigger reflex if |x| > this
        self.x = 0.5                          # current physiological state

        # Active inference model parameters
        self.sigma2_s = 1.0                   # likelihood variance
        self.sigma2_prior = 1.0               # prior variance around safe state
        self.mu_prior = 0.0                   # prior mean (safe state)

        self.disturbance = 0.05               # constant environmental push
        self.action_effect = 0.02             # effect of one action step

        # Reflex parameters (ultrastable mechanism)
        self.reflex_strength = 0.5            # large correction when threatened

    def update_belief(self, x):
        """Bayesian belief update: returns posterior mean and variance."""
        prior_prec = 1.0 / self.sigma2_prior
        like_prec  = 1.0 / self.sigma2_s
        post_prec  = prior_prec + like_prec
        post_var   = 1.0 / post_prec
        post_mean  = (prior_prec * self.mu_prior + like_prec * x) / post_prec
        return post_mean, post_var

    def expected_free_energy(self, predicted_x, action):
        """Expected free energy of an action (anticipatory self-preservation)."""
        x_next = predicted_x + action * self.action_effect + self.disturbance
        mu_pred, var_pred = self.update_belief(x_next)
        # risk = squared deviation of predicted mean from safe state (0)
        # plus the uncertainty (var_pred) – both drive action to reduce G
        risk = mu_pred**2 + var_pred
        return risk

    def step(self):
        # 1. Perception (update belief about current state)
        mu_current, var_current = self.update_belief(self.x)

        # 2. Action selection: anticipatory (active inference) or reactive (reflex)
        if abs(self.x) > self.V_REFLEX:
            # Ultrastable reflex: strongly push toward safe state (0)
            action = -1 if self.x > 0 else +1
            effect = self.reflex_strength  # large, immediate correction
            reflex_triggered = True
        else:
            # Deliberate active inference: choose action that minimises expected free energy
            G_down = self.expected_free_energy(self.x, -1)
            G_up   = self.expected_free_energy(self.x, +1)
            action = -1 if G_down < G_up else +1
            effect = self.action_effect
            reflex_triggered = False

        # 3. Act + environment
        self.x = self.x + action * effect + self.disturbance

        return self.x, reflex_triggered

    def run(self, steps=2000):
        print("Immortal Dual-Layer Cybernetic Organism")
        print("Layer 1: Active inference (anticipatory)")
        print("Layer 2: Ultrastable reflex (reactive)")
        print(f"Goal: keep |x| < {self.V_MAX}  (reflex triggers at |x| > {self.V_REFLEX})")
        for t in range(steps):
            x, reflex = self.step()
            if t % 200 == 0:
                status = "VIABLE" if abs(x) < self.V_MAX else "DEAD"
                tag = " [REFLEX]" if reflex else ""
                print(f"Step {t:4d}: x={x:+.4f}  {status}{tag}")
        print(f"Final x = {self.x:.4f}  {'Viable' if abs(self.x) < self.V_MAX else 'Died'}")
        print("Organism completed.")

if __name__ == "__main__":
    organism = ImmortalHomeostat()
    organism.run()
