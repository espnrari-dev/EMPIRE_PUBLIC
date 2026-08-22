#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
import math
from typing import List

# ============================================================
# AEGIS V13 – NONLINEAR DISCOVERY (No external libs)
# ============================================================
#
# Uses delay embedding + sparse regression (SINDy) to
# discover nonlinear ODE from raw sensor data.
# No PyTorch, no sklearn. Pure NumPy.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (Duffing oscillator)
# -----------------------------------------------------------------
class HiddenRealityV13:
    def __init__(self):
        self.pos = 0.5
        self.vel = 0.0
        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        # Nonlinear mixing
        self.M = np.array([
            [0.8, 0.2],
            [-0.3, 0.9],
            [0.5, -0.6],
            [0.1, 0.7],
            [-0.9, 0.4]
        ])
        self.bias = np.array([0.2, -0.1, 0.3, -0.2, 0.1])
        self.time = 0

    def step(self, dt: float = 0.05) -> List[float]:
        accel = -self.delta * self.vel - self.alpha * self.pos - self.beta * (self.pos**3)
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        state = np.array([self.pos, self.vel])
        raw = np.tanh(self.M @ state + self.bias) + np.random.normal(0, 0.02, size=5)
        return raw.tolist()

# -----------------------------------------------------------------
# 2. AEGIS V13 ENGINE (Pure NumPy)
# -----------------------------------------------------------------
class AEGIS_V13:
    def __init__(self):
        self.raw_data = None
        self.latent_trajectory = None
        self.discovered_eq = None
        self.validation_error = None

    def ingest(self, data: List[List[float]]):
        self.raw_data = np.array(data, dtype=np.float64)
        print(f"[INGEST] Received {len(data)} timesteps of {self.raw_data.shape[1]}-D raw data.")

    # -----------------------------------------------------------------
    # PHASE 1: DELAY EMBEDDING (Takens' theorem)
    # -----------------------------------------------------------------
    def embed(self, delay: int = 1, dimension: int = 2):
        """
        Create a delay embedding from the first sensor (or average of sensors).
        We'll use the first sensor for simplicity; could also use PCA on sensors.
        """
        print("[EMBED] Reconstructing latent space via delay embedding...")
        # Use the first raw sensor (could be any)
        signal = self.raw_data[:, 0]
        T = len(signal)
        # Build embedding: [x(t), x(t+delay), ..., x(t+(dim-1)*delay)]
        embedded = []
        max_idx = T - (dimension - 1) * delay
        for i in range(max_idx):
            vec = [signal[i + j * delay] for j in range(dimension)]
            embedded.append(vec)
        self.latent_trajectory = np.array(embedded)
        print(f"[EMBED] Latent space dimension: {self.latent_trajectory.shape[1]}")
        print(f"[EMBED] Number of points: {self.latent_trajectory.shape[0]}")

    # -----------------------------------------------------------------
    # PHASE 2: SPARSE REGRESSION (SINDy) – custom implementation
    # -----------------------------------------------------------------
    def sindy(self, dt: float = 0.05, threshold: float = 0.05):
        """
        Build library of candidate functions and fit sparse model.
        Uses iterative hard-thresholding (least squares + threshold).
        """
        print("[SINDy] Discovering nonlinear ODE from latent trajectory...")
        z = self.latent_trajectory
        T, d = z.shape

        # Compute derivatives via central difference
        dz = np.gradient(z, dt, axis=0)

        # Use all points for regression
        X = z
        dX = dz

        # Build feature library: polynomial up to degree 3
        # Terms: 1, x, y, x^2, xy, y^2, x^3, x^2 y, x y^2, y^3
        x = X[:, 0:1]
        y = X[:, 1:2] if d >= 2 else np.zeros_like(x)
        features = np.hstack([
            np.ones_like(x),
            x, y,
            x**2, x*y, y**2,
            x**3, (x**2)*y, x*(y**2), y**3
        ])
        term_names = ['1', 'x', 'y', 'x^2', 'xy', 'y^2', 'x^3', 'x^2 y', 'x y^2', 'y^3']

        # Sparse regression for each derivative component
        coeffs_list = []
        for k in range(d):
            target = dX[:, k]
            # Least squares solution
            coeffs = np.linalg.lstsq(features, target, rcond=None)[0]
            # Hard thresholding iteration
            for _ in range(5):
                small = np.abs(coeffs) < threshold
                coeffs[small] = 0
                # Refit only active terms
                active = ~small
                if not np.any(active):
                    break
                coeffs_active = np.linalg.lstsq(features[:, active], target, rcond=None)[0]
                coeffs[active] = coeffs_active
            coeffs_list.append(coeffs)

        # Display discovered equations
        print("[SINDy] Discovered equations:")
        for k, coeffs in enumerate(coeffs_list):
            active = np.where(np.abs(coeffs) > 1e-6)[0]
            terms = [f"{coeffs[i]:.3f}*{term_names[i]}" for i in active]
            eq = f"dz{k+1}/dt = " + " + ".join(terms) if terms else "dz{k+1}/dt = 0"
            print(f"  {eq}")

        # Store coefficients for later use
        self.coeffs = coeffs_list
        self.term_names = term_names

    # -----------------------------------------------------------------
    # PHASE 3: VALIDATION – integrate and reconstruct raw sensors
    # -----------------------------------------------------------------
    def validate(self, dt: float = 0.05):
        """
        Integrate discovered ODE from initial condition,
        project back to raw space using a linear mapping,
        and compute RMSE on raw sensors.
        """
        print("[VALIDATION] Testing discovered model...")
        z0 = self.latent_trajectory[0, :]
        T = len(self.raw_data)
        # Reconstruct latent trajectory
        z_recon = [z0]
        for _ in range(T - len(z_recon)):
            z_curr = z_recon[-1]
            # Compute derivatives using discovered coeffs
            # Build feature vector for current state
            x, y = z_curr[0], z_curr[1] if len(z_curr) > 1 else 0.0
            feats = np.array([1, x, y, x**2, x*y, y**2, x**3, (x**2)*y, x*(y**2), y**3])
            dz_curr = np.array([
                np.dot(self.coeffs[0], feats),
                np.dot(self.coeffs[1], feats) if len(self.coeffs) > 1 else 0.0
            ])
            z_next = z_curr + dz_curr * dt
            z_recon.append(z_next)
        z_recon = np.array(z_recon)

        # We need to map latent states back to raw sensor space.
        # Since we used delay embedding from the first sensor, we can
        # reconstruct the first sensor directly from the first latent variable.
        # But we want all 5 sensors. We'll learn a linear mapping from
        # the latent trajectory (and maybe its lags) to the raw sensors.
        # This is the same as in V12: we fit raw ≈ latent @ A
        latent_full = self.latent_trajectory
        raw_actual = self.raw_data[:len(latent_full)]
        A = np.linalg.lstsq(latent_full, raw_actual, rcond=None)[0]
        raw_recon = z_recon @ A

        # Compute RMSE
        error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
        self.validation_error = error
        print(f"[VALIDATION] Raw sensor reconstruction RMSE: {error:.4f}")

        if error < 0.5:
            print("[PROMOTION] PASSED. Nonlinear dynamics validated.")
            print("[RESULT] AEGIS discovered a nonlinear ODE from raw data without labels.")
        else:
            print("[REJECTED] Reconstruction error too high.")

    # -----------------------------------------------------------------
    # RUN
    # -----------------------------------------------------------------
    def run(self, dt: float = 0.05):
        print("="*72)
        print("AEGIS V13 – NONLINEAR DISCOVERY (Pure NumPy)")
        print("Input: 5‑D raw sensor readings (nonlinear mixing).")
        print("Task: Discover 2‑D latent manifold and nonlinear ODE.")
        print("="*72)
        self.embed(delay=1, dimension=2)
        self.sindy(dt=dt, threshold=0.05)
        self.validate(dt=dt)
        print("="*72)

# -----------------------------------------------------------------
# EXPERIMENT
# -----------------------------------------------------------------
def main():
    random.seed(42)
    np.random.seed(42)
    reality = HiddenRealityV13()
    data = []
    for _ in range(200):
        data.append(reality.step(dt=0.05))
    agent = AEGIS_V13()
    agent.ingest(data)
    agent.run(dt=0.05)

if __name__ == "__main__":
    main()
