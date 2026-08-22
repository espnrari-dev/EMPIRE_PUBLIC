#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
import math
from typing import List, Tuple

# ============================================================
# AEGIS V14 – FIXED NORMALIZATION
# ============================================================
# Same architecture, but latent coordinates are normalized
# before SINDy. This keeps coefficients stable and integration
# from exploding.
# ============================================================

class HiddenRealityV14:
    def __init__(self):
        self.pos = 1.0
        self.vel = 0.0
        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        self.M = np.array([
            [0.8, 0.2],
            [-0.3, 0.9],
            [0.5, -0.6],
            [0.1, 0.7],
            [-0.9, 0.4]
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

class AEGIS_V14:
    def __init__(self):
        self.train_raw = None
        self.test_raw = None
        self.train_latent = None
        self.coeffs = None
        self.term_names = None
        self.projection_matrix = None
        self.prediction_error = None
        # Normalization parameters
        self.latent_mean = None
        self.latent_std = None

    def ingest(self, raw_data: List[List[float]], split_ratio: float = 0.7):
        raw_data = np.array(raw_data, dtype=np.float64)
        n = len(raw_data)
        split_idx = int(n * split_ratio)
        self.train_raw = raw_data[:split_idx]
        self.test_raw = raw_data[split_idx:]
        print(f"[INGEST] Total steps: {n}, train: {len(self.train_raw)}, test: {len(self.test_raw)}")

    def embed(self, delay: int = 1, dimension: int = 2):
        print("[EMBED] Reconstructing latent space from training sensors...")
        signal = self.train_raw[:, 0]
        T = len(signal)
        max_idx = T - (dimension - 1) * delay
        embedded = []
        for i in range(max_idx):
            vec = [signal[i + j * delay] for j in range(dimension)]
            embedded.append(vec)
        self.train_latent = np.array(embedded)
        print(f"[EMBED] Latent dimension: {self.train_latent.shape[1]}")
        print(f"[EMBED] Training latent points: {self.train_latent.shape[0]}")

        # Normalize the training latent trajectory
        self.latent_mean = np.mean(self.train_latent, axis=0)
        self.latent_std = np.std(self.train_latent, axis=0) + 1e-8  # avoid division by zero
        self.train_latent_norm = (self.train_latent - self.latent_mean) / self.latent_std
        print("[EMBED] Normalized latent coordinates (zero mean, unit variance).")

    def discover_ode(self, dt: float = 0.05, threshold: float = 0.05):
        print("[SINDy] Discovering ODE from normalized latent trajectory...")
        z = self.train_latent_norm
        T, d = z.shape
        dz = np.gradient(z, dt, axis=0)

        x = z[:, 0:1]
        y = z[:, 1:2] if d >= 2 else np.zeros_like(x)
        features = np.hstack([
            np.ones_like(x),          # 1
            x, y,
            x**2, x*y, y**2,
            x**3, (x**2)*y, x*(y**2), y**3
        ])
        self.term_names = ['1', 'x', 'y', 'x^2', 'xy', 'y^2', 'x^3', 'x^2 y', 'x y^2', 'y^3']

        coeffs_list = []
        for k in range(d):
            target = dz[:, k]
            coeffs = np.linalg.lstsq(features, target, rcond=None)[0]
            # Hard thresholding
            for _ in range(5):
                small = np.abs(coeffs) < threshold
                coeffs[small] = 0
                active = ~small
                if not np.any(active):
                    break
                coeffs_active = np.linalg.lstsq(features[:, active], target, rcond=None)[0]
                coeffs[active] = coeffs_active
            coeffs_list.append(coeffs)

        self.coeffs = coeffs_list

        print("[SINDy] Discovered equations (in normalized coordinates):")
        for k, coeffs in enumerate(coeffs_list):
            active = np.where(np.abs(coeffs) > 1e-6)[0]
            terms = [f"{coeffs[i]:.3f}*{self.term_names[i]}" for i in active]
            eq = f"dz{k+1}/dt = " + (" + ".join(terms) if terms else "0")
            print(f"  {eq}")

    def train_projection(self):
        print("[PROJECTION] Learning latent -> sensor mapping...")
        n_points = len(self.train_latent)
        # Use normalized latent for projection as well
        latent_train_norm = self.train_latent_norm
        raw_aligned = self.train_raw[:n_points]
        self.projection_matrix = np.linalg.lstsq(latent_train_norm, raw_aligned, rcond=None)[0]
        raw_recon_train = latent_train_norm @ self.projection_matrix
        train_error = np.sqrt(np.mean((raw_aligned - raw_recon_train)**2))
        print(f"[PROJECTION] Training reconstruction RMSE: {train_error:.4f}")

    def validate_predictive(self, dt: float = 0.05):
        print("[VALIDATION] Integrating discovered ODE over UNSEEN test window...")
        # Normalize the initial condition (last training latent point)
        z0 = self.train_latent[-1, :]
        z0_norm = (z0 - self.latent_mean) / self.latent_std
        n_test = len(self.test_raw)

        z_recon_norm = [z0_norm.copy()]
        for _ in range(n_test - 1):
            z_curr = z_recon_norm[-1]
            x = z_curr[0]
            y = z_curr[1] if len(z_curr) > 1 else 0.0
            feats = np.array([1, x, y, x**2, x*y, y**2, x**3, (x**2)*y, x*(y**2), y**3])
            dz = np.zeros(len(z_curr))
            for k in range(len(z_curr)):
                dz[k] = np.dot(self.coeffs[k], feats)
            z_next = z_curr + dz * dt
            z_recon_norm.append(z_next)

        z_recon_norm = np.asarray(z_recon_norm)
        # Unnormalize the reconstructed latent trajectory
        z_recon = z_recon_norm * self.latent_std + self.latent_mean
        # Project to raw sensors using the projection matrix (trained on normalized latents)
        raw_recon = z_recon_norm @ self.projection_matrix

        raw_actual = self.test_raw
        error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
        self.prediction_error = error
        print(f"[VALIDATION] Held-out test sensor RMSE: {error:.4f}")

        if error < 0.5:
            print("[PROMOTION] PASSED. The discovered ODE successfully predicts the unseen test window.")
            print("[RESULT] AEGIS has discovered a valid nonlinear dynamical system from raw data.")
        else:
            print("[REJECTED] Prediction error too high. The discovered dynamics do not generalize.")

def main():
    random.seed(42)
    np.random.seed(42)

    reality = HiddenRealityV14()
    raw_data = []
    hidden_states = []
    for _ in range(300):
        raw, hidden = reality.step(dt=0.05)
        raw_data.append(raw)
        hidden_states.append(hidden)

    agent = AEGIS_V14()
    agent.ingest(raw_data, split_ratio=0.7)

    print("="*72)
    print("AEGIS V14 – NONLINEAR DISCOVERY (Normalized)")
    print("="*72)

    agent.embed(delay=1, dimension=2)
    agent.discover_ode(dt=0.05, threshold=0.05)
    agent.train_projection()
    agent.validate_predictive(dt=0.05)

    print("="*72)

if __name__ == "__main__":
    main()
