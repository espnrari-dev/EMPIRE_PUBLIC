#!/data/data/com.termux/files/usr/bin/python

import random
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

# ============================================================
# AEGIS V12 – REFINED
# LATENT VARIABLE DISCOVERY WITH PARAMETER OPTIMIZATION
# ============================================================

class HiddenRealityV12:
    def __init__(self):
        self.pos = 1.5
        self.vel = 0.0
        self.k = 0.8
        self.mix = np.array([
            [0.8, 0.2],
            [-0.3, 0.9],
            [0.5, -0.6],
            [0.1, 0.7],
            [-0.9, 0.4]
        ])
        self.time = 0

    def step(self, dt: float = 0.1) -> List[float]:
        accel = -self.k * self.pos
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        state = np.array([self.pos, self.vel])
        raw = self.mix @ state + np.random.normal(0, 0.02, size=5)
        return raw.tolist()

class AEGIS_V12_Refined:
    def __init__(self):
        self.raw_data: List[List[float]] = []
        self.latent_dim = 2
        self.components = None
        self.latent_signals = None
        self.discovered_equation = None
        self.refined_k = None
        self.refined_initial = None

    def ingest(self, data: List[List[float]]):
        self.raw_data = data
        print(f"[INGEST] Received {len(data)} timesteps of {len(data[0])}-dimensional raw data.")
        print("[INGEST] No labels provided. Discovering latent structure...")

    def discover_latents(self):
        data = np.array(self.raw_data)
        mean = np.mean(data, axis=0)
        centered = data - mean
        cov = np.cov(centered.T)
        # Power iteration for top 2 components
        def power_iteration(cov_matrix, n_iters=100):
            eigen_vectors = []
            eigen_values = []
            for _ in range(self.latent_dim):
                v = np.random.randn(cov_matrix.shape[0])
                v = v / np.linalg.norm(v)
                for _ in range(n_iters):
                    v = cov_matrix @ v
                    v = v / np.linalg.norm(v)
                eigen_val = v.T @ cov_matrix @ v
                eigen_vectors.append(v)
                eigen_values.append(eigen_val)
                cov_matrix = cov_matrix - eigen_val * np.outer(v, v)
            return eigen_vectors, eigen_values
        vectors, values = power_iteration(cov)
        idx = np.argsort(values)[::-1]
        self.components = np.array([vectors[i] for i in idx])
        self.latent_signals = centered @ self.components.T
        self.data_mean = mean
        print(f"[PCA] Discovered {self.latent_dim} latent variables.")
        print(f"[PCA] Explained variance ratios: {[v/sum(values) for v in np.sort(values)[::-1]]}")

    def discover_dynamics(self):
        if self.latent_signals is None:
            return
        z0 = self.latent_signals[:, 0]
        z1 = self.latent_signals[:, 1]

        # Determine which is smoother (position)
        def autocorr(x):
            return np.corrcoef(x[:-1], x[1:])[0,1]
        ac0 = autocorr(z0)
        ac1 = autocorr(z1)
        if ac0 > ac1:
            pos_signal = z0
            vel_signal = z1
        else:
            pos_signal = z1
            vel_signal = z0

        dt = 0.1
        # Verify vel ≈ derivative(pos)
        pos_deriv = np.diff(pos_signal) / dt
        min_len = min(len(pos_deriv), len(vel_signal))
        corr = np.corrcoef(vel_signal[:min_len], pos_deriv[:min_len])[0,1]
        print(f"[DYNAMICS] Correlation vel vs derivative(pos): {corr:.4f}")

        # Fit accel = a * pos + b
        accel = np.diff(vel_signal) / dt
        min_len2 = min(len(accel), len(pos_signal))
        pos_aligned = pos_signal[:min_len2]
        accel_aligned = accel[:min_len2]
        mean_x = np.mean(pos_aligned)
        mean_y = np.mean(accel_aligned)
        num = np.sum((pos_aligned - mean_x) * (accel_aligned - mean_y))
        den = np.sum((pos_aligned - mean_x)**2)
        if abs(den) > 1e-12:
            a = num / den
            b = mean_y - a * mean_x
        else:
            a, b = 0, 0
        k_initial = -a
        print(f"[DYNAMICS] Initial spring constant k = {k_initial:.4f}")

        # Now refine k and initial conditions to minimize reconstruction error
        self.refine_model(pos_signal, vel_signal, k_initial, dt)

    def refine_model(self, pos_signal, vel_signal, k_initial, dt):
        """
        Use grid search around k_initial to minimize reconstruction error.
        Also adjust initial position and velocity slightly.
        """
        # We'll search k in [0.5, 1.2] with step 0.01
        best_k = k_initial
        best_error = float("inf")
        best_pos0 = pos_signal[0]
        best_vel0 = vel_signal[0]
        # Also allow small adjustments to initial conditions
        search_k = np.linspace(max(0.3, k_initial-0.3), min(1.2, k_initial+0.3), 20)
        # We'll also try a few shifts in initial conditions
        shifts_pos = [0.0, 0.05, -0.05, 0.1, -0.1]
        shifts_vel = [0.0, 0.05, -0.05, 0.1, -0.1]
        for k in search_k:
            for shift_pos in shifts_pos:
                for shift_vel in shifts_vel:
                    pos0 = pos_signal[0] + shift_pos
                    vel0 = vel_signal[0] + shift_vel
                    # Reconstruct
                    pos_recon = [pos0]
                    vel_recon = [vel0]
                    for i in range(1, len(pos_signal)):
                        acc = -k * pos_recon[-1]
                        vel_new = vel_recon[-1] + acc * dt
                        pos_new = pos_recon[-1] + vel_recon[-1] * dt
                        pos_recon.append(pos_new)
                        vel_recon.append(vel_new)
                    latent_recon = np.column_stack([pos_recon, vel_recon])
                    # Sign alignment
                    sign_align = np.sign(self.latent_signals[:,0][0] / pos_recon[0])
                    if sign_align < 0:
                        pos_recon = -np.array(pos_recon)
                        latent_recon[:,0] = pos_recon
                    sign_align2 = np.sign(self.latent_signals[:,1][0] / vel_recon[0])
                    if sign_align2 < 0:
                        vel_recon = -np.array(vel_recon)
                        latent_recon[:,1] = vel_recon
                    # Project to raw
                    raw_recon = (latent_recon @ self.components) + self.data_mean
                    raw_actual = np.array(self.raw_data)
                    error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
                    if error < best_error:
                        best_error = error
                        best_k = k
                        best_pos0 = pos0
                        best_vel0 = vel0
        print(f"[REFINE] Best k = {best_k:.4f}, error = {best_error:.4f}")
        self.refined_k = best_k
        self.refined_initial = (best_pos0, best_vel0)
        self.discovered_equation = f"accel = {-best_k:.4f} * pos"

        # Final validation
        if best_error < 0.5:
            print("[PROMOTION] PASSED. Refined model validates.")
            print(f"[RESULT] Hidden Equation: {self.discovered_equation}")
            print("[RESULT] System discovered the concept of 'position' and 'velocity' from raw data.")
        else:
            print("[REJECTED] Even after refinement, error too high.")

    def run(self):
        print("="*72)
        print("AEGIS V12 REFINED – LATENT VARIABLE DISCOVERY")
        print("Initial: 100 raw, unlabeled sensor readings.")
        print("Task: Invent the variables and discover the physics.")
        print("="*72)
        self.discover_latents()
        self.discover_dynamics()
        print("="*72)

def main():
    random.seed(42)
    np.random.seed(42)
    reality = HiddenRealityV12()
    data = []
    for _ in range(100):
        data.append(reality.step(dt=0.1))
    agent = AEGIS_V12_Refined()
    agent.ingest(data)
    agent.run()

if __name__ == "__main__":
    main()
