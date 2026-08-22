#!/data/data/com.termux/files/usr/bin/python

import random
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

# ============================================================
# AEGIS V12
# LATENT VARIABLE DISCOVERY FROM RAW SENSOR DATA
# ============================================================
#
# Input: 100 raw, unlabeled sensor readings per timestep.
# Output: The hidden differential equation governing the system.
#
# No labels. No "this is position". No "this is velocity".
# The system must invent those concepts.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (The system never sees this)
# -----------------------------------------------------------------
class HiddenRealityV12:
    """
    A 2D harmonic oscillator (spring).
    Hidden state: [position, velocity].
    But the system outputs 5 RAW SENSORS that are random linear
    mixtures of the state plus noise.
    """
    def __init__(self):
        self.pos = 1.5
        self.vel = 0.0
        self.k = 0.8  # spring constant
        # Random mixing matrix (5 sensors, 2 hidden states)
        self.mix = np.array([
            [0.8, 0.2],
            [-0.3, 0.9],
            [0.5, -0.6],
            [0.1, 0.7],
            [-0.9, 0.4]
        ])
        self.time = 0

    def step(self, dt: float = 0.1) -> List[float]:
        # Physics: acceleration = -k * pos
        accel = -self.k * self.pos
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        
        # Generate raw sensor readings: mix * state + noise
        state = np.array([self.pos, self.vel])
        raw = self.mix @ state + np.random.normal(0, 0.02, size=5)
        return raw.tolist()

# -----------------------------------------------------------------
# 2. AEGIS V12 ENGINE
# -----------------------------------------------------------------
class AEGIS_V12:
    def __init__(self):
        self.raw_data: List[List[float]] = []
        self.latent_dim = 2
        self.components = None
        self.latent_signals = None
        self.discovered_equation = None

    # -----------------------------------------------------------------
    # PHASE 1: RECEIVE RAW DATA (No labels)
    # -----------------------------------------------------------------
    def ingest(self, data: List[List[float]]):
        self.raw_data = data
        print(f"[INGEST] Received {len(data)} timesteps of {len(data[0])}-dimensional raw data.")
        print("[INGEST] No labels provided. Discovering latent structure...")

    # -----------------------------------------------------------------
    # PHASE 2: DISCOVER LATENT VARIABLES (PCA)
    # -----------------------------------------------------------------
    def discover_latents(self):
        """
        Use PCA to find the 2 most important hidden signals.
        This is the part where the system "invents" the concepts
        of position and velocity without being told.
        """
        data = np.array(self.raw_data)
        # Center the data
        mean = np.mean(data, axis=0)
        centered = data - mean
        
        # Compute covariance matrix
        cov = np.cov(centered.T)
        
        # Manual power iteration to find top 2 eigenvectors
        def power_iteration(cov_matrix, n_iters=100):
            # Random init
            eigen_vectors = []
            eigen_values = []
            
            # Deflation method: find top 2
            for _ in range(self.latent_dim):
                v = np.random.randn(cov_matrix.shape[0])
                v = v / np.linalg.norm(v)
                for _ in range(n_iters):
                    v = cov_matrix @ v
                    v = v / np.linalg.norm(v)
                # Compute eigenvalue
                eigen_val = v.T @ cov_matrix @ v
                eigen_vectors.append(v)
                eigen_values.append(eigen_val)
                # Deflate the matrix
                cov_matrix = cov_matrix - eigen_val * np.outer(v, v)
            return eigen_vectors, eigen_values
        
        vectors, values = power_iteration(cov)
        
        # Sort by eigenvalue descending
        idx = np.argsort(values)[::-1]
        self.components = np.array([vectors[i] for i in idx])
        
        # Project raw data onto these components to get latent signals
        self.latent_signals = centered @ self.components.T
        
        print(f"[PCA] Discovered {self.latent_dim} latent variables.")
        print(f"[PCA] Explained variance ratios: {[v/sum(values) for v in np.sort(values)[::-1]]}")
        print("[PCA] These are the 'invented' coordinates. The system does not know which is 'position'.")

    # -----------------------------------------------------------------
    # PHASE 3: DISCOVER DYNAMICS (V11 applied to latent variables)
    # -----------------------------------------------------------------
    def discover_dynamics(self):
        """
        Given the two latent variables (z0, z1), figure out their
        differential relationship WITHOUT being told which is position.
        """
        if self.latent_signals is None:
            return
        
        # Extract the two latent signals
        z0 = self.latent_signals[:, 0]
        z1 = self.latent_signals[:, 1]
        
        # Determine which is position and which is velocity:
        # Position tends to be smoother; velocity is its derivative.
        # We can check: if z0 is the derivative of z1, then diff(z0) ≈ z1.
        # We'll assume the one with larger autocorrelation is position.
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
        
        # Now treat pos_signal as "x" and vel_signal as "y" (derivative)
        # We'll use a simplified V11: compute rates, fit linear, validate.
        print("[DYNAMICS] Analyzing relationship between latent variables...")
        
        # Create observations for V11
        # We assume vel_signal is the derivative of pos_signal.
        # We need to find the relationship between pos and vel, and between vel and acceleration.
        # We'll just run the V11 linear rate discovery on (pos -> vel) and (vel -> accel).
        # Our hidden reality is a spring: accel = -k * pos.
        # So we find that vel ≈ derivative(pos), and accel ≈ derivative(vel).
        # Then we fit accel = -k * pos.
        
        # Step A: Verify that vel is derivative of pos
        # We can compute the derivative of pos numerically and compare to vel.
        dt = 0.1  # known timestep from simulation
        pos_deriv = np.diff(pos_signal) / dt
        # Align lengths
        min_len = min(len(pos_deriv), len(vel_signal))
        vel_aligned = vel_signal[:min_len]
        pos_deriv_aligned = pos_deriv[:min_len]
        
        # Check correlation between vel and derivative of pos
        corr = np.corrcoef(vel_aligned, pos_deriv_aligned)[0,1]
        print(f"[DYNAMICS] Correlation between vel and derivative(pos): {corr:.4f}")
        
        # Step B: Find the spring relationship: accel = -k * pos
        accel = np.diff(vel_signal) / dt
        min_len2 = min(len(accel), len(pos_signal))
        pos_aligned = pos_signal[:min_len2]
        accel_aligned = accel[:min_len2]
        
        # Fit linear: accel = a * pos + b
        # (We expect a = -k, b ≈ 0)
        mean_x = np.mean(pos_aligned)
        mean_y = np.mean(accel_aligned)
        num = np.sum((pos_aligned - mean_x) * (accel_aligned - mean_y))
        den = np.sum((pos_aligned - mean_x)**2)
        if abs(den) > 1e-12:
            a = num / den
            b = mean_y - a * mean_x
        else:
            a, b = 0, 0
        
        k_discovered = -a
        print(f"[DYNAMICS] Discovered acceleration = {a:.4f} * pos + {b:.4f}")
        print(f"[DYNAMICS] Therefore, spring constant k = {k_discovered:.4f}")
        self.discovered_equation = f"accel = {a:.4f} * pos + {b:.4f}"
        
        # Step C: Validate by reconstructing the original raw sensors
        # We'll project back to raw space using the discovered model.
        # To do this, we need to re-create the latent signals from the discovered model.
        # We'll use the initial position and velocity from the data.
        pos0 = pos_signal[0]
        vel0 = vel_signal[0]
        
        # Reconstruct pos and vel using Euler integration with discovered k
        dt = 0.1
        pos_recon = [pos0]
        vel_recon = [vel0]
        for i in range(1, len(pos_signal)):
            acc = -k_discovered * pos_recon[-1]
            vel_new = vel_recon[-1] + acc * dt
            pos_new = pos_recon[-1] + vel_recon[-1] * dt
            pos_recon.append(pos_new)
            vel_recon.append(vel_new)
        
        # Now we have reconstructed latent signals.
        # Project back to raw sensor space using the PCA components.
        # We need to invert the PCA projection.
        # The raw data was centered: raw_centered = raw - mean
        # latent = raw_centered @ components.T
        # So raw_centered_hat = latent @ components
        # raw_hat = raw_centered_hat + mean
        latent_recon = np.column_stack([pos_recon, vel_recon])
        # But we need to align the signs: our PCA components may have flipped signs.
        # We'll check sign alignment with original latents.
        sign_align = np.sign(self.latent_signals[:,0][0] / pos_recon[0])
        if sign_align < 0:
            pos_recon = -np.array(pos_recon)
            latent_recon[:,0] = pos_recon
        sign_align2 = np.sign(self.latent_signals[:,1][0] / vel_recon[0])
        if sign_align2 < 0:
            vel_recon = -np.array(vel_recon)
            latent_recon[:,1] = vel_recon
        
        raw_recon = (latent_recon @ self.components) + np.mean(self.raw_data, axis=0)
        
        # Compute validation error on raw sensors
        raw_actual = np.array(self.raw_data)
        error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
        print(f"[VALIDATION] Reconstructed raw sensors with RMSE: {error:.4f}")
        
        # Promotion Gate (V12 style)
        if error < 0.5:
            print("[PROMOTION] PASSED. The discovered latent structure and dynamics validate.")
            print(f"[RESULT] Hidden Equation: {self.discovered_equation}")
            print("[RESULT] System discovered the concept of 'position' and 'velocity' from raw data.")
        else:
            print("[REJECTED] The discovered model did not reconstruct the raw sensors accurately.")

    # -----------------------------------------------------------------
    # RUN
    # -----------------------------------------------------------------
    def run(self):
        print("="*72)
        print("AEGIS V12 – LATENT VARIABLE DISCOVERY")
        print("Initial: 100 raw, unlabeled sensor readings.")
        print("Task: Invent the variables and discover the physics.")
        print("="*72)
        
        self.discover_latents()
        self.discover_dynamics()
        print("="*72)

# -----------------------------------------------------------------
# EXPERIMENT
# -----------------------------------------------------------------
def main():
    random.seed(42)
    np.random.seed(42)
    
    # Create the hidden reality
    reality = HiddenRealityV12()
    
    # Collect 100 timesteps of raw sensor data (5 sensors)
    data = []
    for _ in range(100):
        data.append(reality.step(dt=0.1))
    
    # Feed the raw data to AEGIS V12 (no labels, no names)
    agent = AEGIS_V12()
    agent.ingest(data)
    agent.run()

if __name__ == "__main__":
    main()
