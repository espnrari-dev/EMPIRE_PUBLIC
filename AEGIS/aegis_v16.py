#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
from typing import List, Tuple

# ============================================================
# AEGIS V16 – IDENTIFIABILITY TEST
# ============================================================
#
# Same exact discovery pipeline as V15.
# Then we compare the discovered latent trajectory to
# the true hidden [position, velocity] state.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (Duffing oscillator - same as V15)
# -----------------------------------------------------------------
class HiddenRealityV16:
    def __init__(self):
        self.pos = 1.0
        self.vel = 0.0
        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        self.M = np.array([
            [0.8, 0.2], [-0.3, 0.9], [0.5, -0.6], [0.1, 0.7], [-0.9, 0.4]
        ])
        self.bias = np.array([0.2, -0.1, 0.3, -0.2, 0.1])
        self.time = 0
        self.hidden_states = []

    def step(self, dt: float = 0.05) -> Tuple[List[float], List[float]]:
        accel = -self.delta * self.vel - self.alpha * self.pos - self.beta * (self.pos**3)
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        self.hidden_states.append([self.pos, self.vel])
        state = np.array([self.pos, self.vel])
        raw = np.tanh(self.M @ state + self.bias) + np.random.normal(0, 0.02, size=5)
        return raw.tolist(), [self.pos, self.vel]

# -----------------------------------------------------------------
# 2. AEGIS V16 ENGINE (Identical discovery to V15)
# -----------------------------------------------------------------
class AEGIS_V16:
    def __init__(self):
        self.train_raw = None
        self.test_raw = None
        self.train_latent = None
        self.coeffs = None
        self.projection_matrix = None
        self.latent_mean = None
        self.latent_std = None
        self.hidden_states_train = None
        self.hidden_states_test = None

    def ingest(self, raw_data: List[List[float]], hidden_data: List[List[float]], split_ratio: float = 0.7):
        raw_data = np.array(raw_data, dtype=np.float64)
        hidden_data = np.array(hidden_data, dtype=np.float64)
        n = len(raw_data)
        split_idx = int(n * split_ratio)
        self.train_raw = raw_data[:split_idx]
        self.test_raw = raw_data[split_idx:]
        self.hidden_states_train = hidden_data[:split_idx]
        self.hidden_states_test = hidden_data[split_idx:]
        print(f"[INGEST] Train: {len(self.train_raw)}, Test: {len(self.test_raw)}")

    def embed(self, delay: int = 1, dimension: int = 2):
        signal = self.train_raw[:, 0]
        T = len(signal)
        max_idx = T - (dimension - 1) * delay
        embedded = []
        for i in range(max_idx):
            vec = [signal[i + j * delay] for j in range(dimension)]
            embedded.append(vec)
        self.train_latent = np.array(embedded)
        self.latent_mean = np.mean(self.train_latent, axis=0)
        self.latent_std = np.std(self.train_latent, axis=0) + 1e-8
        self.train_latent_norm = (self.train_latent - self.latent_mean) / self.latent_std
        print(f"[EMBED] Latent dim: {self.train_latent.shape[1]}, Points: {self.train_latent.shape[0]}")

    def discover_ode(self, dt: float = 0.05, threshold: float = 0.05):
        z = self.train_latent_norm
        dz = np.gradient(z, dt, axis=0)
        x, y = z[:, 0:1], z[:, 1:2]
        features = np.hstack([np.ones_like(x), x, y, x**2, x*y, y**2])
        term_names = ['1', 'x', 'y', 'x^2', 'xy', 'y^2']
        coeffs_list = []
        for k in range(z.shape[1]):
            target = dz[:, k]
            coeffs = np.linalg.lstsq(features, target, rcond=None)[0]
            for _ in range(5):
                small = np.abs(coeffs) < threshold
                coeffs[small] = 0
                if not np.any(~small): break
                active = ~small
                coeffs[active] = np.linalg.lstsq(features[:, active], target, rcond=None)[0]
            coeffs_list.append(coeffs)
        self.coeffs = coeffs_list
        print("[SINDy] Equations (normalized):")
        for k, c in enumerate(coeffs_list):
            active = np.where(np.abs(c) > 1e-6)[0]
            print(f"  dz{k+1}/dt = " + " + ".join([f"{c[i]:.3f}*{term_names[i]}" for i in active]))

    def train_projection(self):
        n = len(self.train_latent)
        raw_aligned = self.train_raw[:n]
        self.projection_matrix = np.linalg.lstsq(self.train_latent_norm, raw_aligned, rcond=None)[0]
        recon = self.train_latent_norm @ self.projection_matrix
        print(f"[PROJECTION] Train recon RMSE: {np.sqrt(np.mean((raw_aligned - recon)**2)):.6f}")

    # -----------------------------------------------------------------
    # RK4 INTEGRATION (autonomous rollout)
    # -----------------------------------------------------------------
    def integrate(self, z0_norm, n_steps, dt: float = 0.05):
        z = z0_norm.copy()
        traj = [z.copy()]
        for _ in range(n_steps - 1):
            z_curr = traj[-1]
            x, y = z_curr[0], z_curr[1]
            feats = np.array([1, x, y, x**2, x*y, y**2])
            
            def f(z):
                x, y = z[0], z[1]
                feats = np.array([1, x, y, x**2, x*y, y**2])
                return np.array([np.dot(self.coeffs[0], feats), np.dot(self.coeffs[1], feats)])
            
            # RK4
            k1 = f(z_curr)
            k2 = f(z_curr + 0.5 * dt * k1)
            k3 = f(z_curr + 0.5 * dt * k2)
            k4 = f(z_curr + dt * k3)
            z_next = z_curr + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
            traj.append(z_next)
        return np.array(traj)

    def validate_predictive(self, dt: float = 0.05):
        z0_norm = (self.train_latent[-1] - self.latent_mean) / self.latent_std
        n_test = len(self.test_raw)
        z_recon_norm = self.integrate(z0_norm, n_test, dt)
        raw_recon = z_recon_norm @ self.projection_matrix
        error = np.sqrt(np.mean((self.test_raw - raw_recon)**2))
        print(f"[VALIDATION] Held-out sensor RMSE: {error:.6f}")
        return z_recon_norm, error

    # -----------------------------------------------------------------
    # V16: IDENTIFIABILITY TEST (Compare latent to hidden state)
    # -----------------------------------------------------------------
    def identifiability_test(self, dt: float = 0.05):
        print("\n" + "="*72)
        print("[IDENTIFIABILITY] Comparing discovered latent to true hidden state...")
        
        # 1. Get the full discovered latent trajectory (training + test)
        # We need the latent trajectory over the training period first.
        # We have self.train_latent for training. For test, we use the RK4 rollout from the last training point.
        z0_norm = (self.train_latent[-1] - self.latent_mean) / self.latent_std
        n_test = len(self.test_raw)
        z_test_recon_norm = self.integrate(z0_norm, n_test, dt)
        z_test_recon = z_test_recon_norm * self.latent_std + self.latent_mean
        
        # Concatenate full discovered latent trajectory
        z_full_discovered = np.vstack([self.train_latent, z_test_recon])
        
        # 2. Get the full true hidden trajectory (training + test)
        # The hidden states are stored sequentially. We must align them.
        # The embedding produced train_latent of length T_emb. 
        # The hidden states are of length T_raw. We align by slicing hidden to match the embedding window.
        # For simplicity, we slice hidden to match the number of latent points we have.
        n_latent = len(z_full_discovered)
        hidden_full = np.vstack([self.hidden_states_train, self.hidden_states_test])
        hidden_aligned = hidden_full[:n_latent]  # Align lengths
        
        # 3. Learn a linear mapping from discovered latent to true hidden state.
        # We use the training portion to fit the mapping.
        n_train_latent = len(self.train_latent)
        latent_train = z_full_discovered[:n_train_latent]
        hidden_train = hidden_aligned[:n_train_latent]
        
        # Fit: hidden ≈ latent @ W + b
        # Add intercept column
        latent_train_aug = np.hstack([latent_train, np.ones((n_train_latent, 1))])
        W, _, _, _ = np.linalg.lstsq(latent_train_aug, hidden_train, rcond=None)
        
        # 4. Apply mapping to the full latent trajectory and compute RMSE
        latent_full_aug = np.hstack([z_full_discovered, np.ones((n_latent, 1))])
        hidden_pred = latent_full_aug @ W
        
        # Compute RMSE on the test portion separately to check generalization
        n_test_latent = n_latent - n_train_latent
        if n_test_latent > 0:
            hidden_test_actual = hidden_aligned[n_train_latent:]
            hidden_test_pred = hidden_pred[n_train_latent:]
            test_ident_error = np.sqrt(np.mean((hidden_test_actual - hidden_test_pred)**2))
            print(f"[IDENTIFIABILITY] Test-set hidden state prediction RMSE: {test_ident_error:.6f}")
            
            # Also compute correlation between predicted and actual hidden states
            corr_pos = np.corrcoef(hidden_test_actual[:, 0], hidden_test_pred[:, 0])[0, 1]
            corr_vel = np.corrcoef(hidden_test_actual[:, 1], hidden_test_pred[:, 1])[0, 1]
            print(f"[IDENTIFIABILITY] Correlation (pos): {corr_pos:.6f}, (vel): {corr_vel:.6f}")
            
            if test_ident_error < 0.2 and corr_pos > 0.95 and corr_vel > 0.95:
                print("[RESULT] STRONG IDENTIFIABILITY: The discovered latent space is essentially a linear transformation of the true physical state.")
            else:
                print("[RESULT] WEAK IDENTIFIABILITY: The discovered latent space is predictive but not trivially mappable to the true physical coordinates.")
        else:
            print("[IDENTIFIABILITY] Not enough test latent points to evaluate.")

# -----------------------------------------------------------------
# 3. EXPERIMENT
# -----------------------------------------------------------------
def main():
    random.seed(42)
    np.random.seed(42)

    reality = HiddenRealityV16()
    raw_data = []
    hidden_data = []
    for _ in range(300):
        raw, hidden = reality.step(dt=0.05)
        raw_data.append(raw)
        hidden_data.append(hidden)

    agent = AEGIS_V16()
    agent.ingest(raw_data, hidden_data, split_ratio=0.7)

    print("="*72)
    print("AEGIS V16 – IDENTIFIABILITY TEST")
    print("="*72)
    
    agent.embed(delay=1, dimension=2)
    agent.discover_ode(dt=0.05, threshold=0.05)
    agent.train_projection()
    agent.validate_predictive(dt=0.05)
    agent.identifiability_test(dt=0.05)
    
    print("="*72)

if __name__ == "__main__":
    main()
