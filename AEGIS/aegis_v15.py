#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
from typing import List, Tuple

# ============================================================
# AEGIS V15 – STABLE NONLINEAR PREDICTION
# ============================================================
# Raw sensors → delay embedding → normalized latent space
# → quadratic SINDy → RK4 integration → sensor projection
# → held-out validation
# ============================================================

class HiddenRealityV15:
    def __init__(self):
        self.pos = 1.0
        self.vel = 0.0
        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        self.M = np.array([
            [0.8, 0.2], [-0.3, 0.9], [0.5, -0.6],
            [0.1, 0.7], [-0.9, 0.4]
        ])
        self.bias = np.array([0.2, -0.1, 0.3, -0.2, 0.1])
        self.time = 0
        self.hidden_states = []

    def step(self, dt: float = 0.05) -> Tuple[List[float], List[float]]:
        accel = -self.delta * self.vel - self.alpha * self.pos - self.beta * (self.pos ** 3)
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        self.hidden_states.append([self.pos, self.vel])
        state = np.array([self.pos, self.vel])
        raw = np.tanh(self.M @ state + self.bias) + np.random.normal(0, 0.02, size=5)
        return raw.tolist(), [self.pos, self.vel]


class AEGIS_V15:
    def __init__(self):
        self.train_raw = None
        self.test_raw = None
        self.train_latent = None
        self.coeffs = None
        self.projection_matrix = None
        self.latent_mean = None
        self.latent_std = None

    def ingest(self, raw_data: List[List[float]], split_ratio: float = 0.7):
        raw_data = np.array(raw_data, dtype=np.float64)
        n = len(raw_data)
        split_idx = int(n * split_ratio)
        self.train_raw = raw_data[:split_idx]
        self.test_raw = raw_data[split_idx:]
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
                if not np.any(~small):
                    break
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
        rmse = np.sqrt(np.mean((raw_aligned - recon) ** 2))
        print(f"[PROJECTION] Train recon RMSE: {rmse:.6f}")

    def integrate_rk4(self, z0_norm, n_steps, dt: float = 0.05):
        z = z0_norm.copy()
        traj = [z.copy()]
        for _ in range(n_steps - 1):
            z_curr = traj[-1]
            def f(z):
                x, y = z[0], z[1]
                feats = np.array([1, x, y, x**2, x*y, y**2])
                return np.array([np.dot(self.coeffs[0], feats),
                                 np.dot(self.coeffs[1], feats)])
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
        z_recon_norm = self.integrate_rk4(z0_norm, n_test, dt)
        raw_recon = z_recon_norm @ self.projection_matrix
        error = np.sqrt(np.mean((self.test_raw - raw_recon) ** 2))
        print(f"[VALIDATION] Held-out sensor RMSE: {error:.6f}")
        if error < 0.5:
            print("[PROMOTION] PASSED. Stable nonlinear prediction.")
        else:
            print("[REJECTED] Prediction error too high.")
        return error

    def run(self, dt: float = 0.05):
        print("=" * 72)
        print("AEGIS V15 – STABLE NONLINEAR PREDICTION")
        print("=" * 72)
        self.embed()
        self.discover_ode(dt=dt)
        self.train_projection()
        self.validate_predictive(dt=dt)
        print("=" * 72)


def main():
    random.seed(42)
    np.random.seed(42)

    reality = HiddenRealityV15()
    raw_data = []
    for _ in range(300):
        raw, _ = reality.step(dt=0.05)
        raw_data.append(raw)

    agent = AEGIS_V15()
    agent.ingest(raw_data, split_ratio=0.7)
    agent.run(dt=0.05)


if __name__ == "__main__":
    main()
