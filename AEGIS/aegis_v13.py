#!/data/data/com.termux/files/usr/bin/python

import random
import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.linear_model import Lasso
from typing import List, Tuple, Optional

# ============================================================
# AEGIS V13 – NONLINEAR LATENT DYNAMICS DISCOVERY
# ============================================================
#
# Input:  100 timesteps of 5‑dimensional raw sensor data.
# Task:   Discover a 2‑D latent space (nonlinear) and the
#         governing nonlinear differential equations.
# Output: Validated ODE: dx/dt = f(x,y), dy/dt = g(x,y)
#         and ability to reconstruct raw sensors.
#
# No labels, no hints about nonlinearity.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (Nonlinear Duffing oscillator)
# -----------------------------------------------------------------
class HiddenRealityV13:
    """
    Duffing oscillator: x'' = -δ x' - α x - β x^3
    with δ = 0.1, α = -1.0 (negative stiffness), β = 1.0.
    We'll use two state variables: position and velocity.
    The raw sensors are a nonlinear mixture (tanh) of the state.
    """
    def __init__(self):
        self.pos = 0.5
        self.vel = 0.0
        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        # Nonlinear mixing: 5 sensors = tanh( M @ state + bias )
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
        # Duffing acceleration
        accel = -self.delta * self.vel - self.alpha * self.pos - self.beta * (self.pos**3)
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        # Nonlinear mixing
        state = np.array([self.pos, self.vel])
        raw = np.tanh(self.M @ state + self.bias) + np.random.normal(0, 0.02, size=5)
        return raw.tolist()

# -----------------------------------------------------------------
# 2. SIMPLE AUTOENCODER (PyTorch)
# -----------------------------------------------------------------
class Autoencoder(nn.Module):
    def __init__(self, input_dim=5, latent_dim=2):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 10),
            nn.Tanh(),
            nn.Linear(10, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 10),
            nn.Tanh(),
            nn.Linear(10, input_dim)
        )
    def forward(self, x):
        z = self.encoder(x)
        x_hat = self.decoder(z)
        return z, x_hat

# -----------------------------------------------------------------
# 3. AEGIS V13 ENGINE
# -----------------------------------------------------------------
class AEGIS_V13:
    def __init__(self):
        self.raw_data = None
        self.latent_dim = 2
        self.autoencoder = None
        self.latent_trajectory = None   # shape (T, 2)
        self.discovered_odes = None     # list of (coeffs, terms)
        self.validation_error = None

    # -----------------------------------------------------------------
    # PHASE 1: INGEST RAW DATA (unlabeled)
    # -----------------------------------------------------------------
    def ingest(self, data: List[List[float]]):
        self.raw_data = np.array(data, dtype=np.float32)
        print(f"[INGEST] Received {len(data)} timesteps of {self.raw_data.shape[1]}-D raw data.")

    # -----------------------------------------------------------------
    # PHASE 2: TRAIN AUTOENCODER (nonlinear latent discovery)
    # -----------------------------------------------------------------
    def train_autoencoder(self, epochs=1000, lr=0.01):
        print("[AUTOENCODER] Training to discover nonlinear latent variables...")
        data_tensor = torch.tensor(self.raw_data)
        self.autoencoder = Autoencoder(input_dim=self.raw_data.shape[1], latent_dim=self.latent_dim)
        optimizer = optim.Adam(self.autoencoder.parameters(), lr=lr)
        criterion = nn.MSELoss()
        for epoch in range(epochs):
            optimizer.zero_grad()
            z, x_hat = self.autoencoder(data_tensor)
            loss = criterion(x_hat, data_tensor)
            loss.backward()
            optimizer.step()
            if epoch % 200 == 0:
                print(f"  Epoch {epoch:4d} | reconstruction loss: {loss.item():.6f}")
        # Store latent trajectory
        with torch.no_grad():
            z, _ = self.autoencoder(data_tensor)
            self.latent_trajectory = z.numpy()
        print(f"[AUTOENCODER] Latent space discovered. Shape: {self.latent_trajectory.shape}")

    # -----------------------------------------------------------------
    # PHASE 3: DISCOVER NONLINEAR ODE via SINDy
    # -----------------------------------------------------------------
    def discover_odes(self):
        """
        Use sparse regression to find dx/dt and dy/dt as functions of x,y.
        Candidate library: [1, x, y, x^2, x*y, y^2, x^3, x^2*y, x*y^2, y^3]
        """
        print("[SINDy] Discovering nonlinear ODE from latent trajectory...")
        T = self.latent_trajectory.shape[0]
        dt = 0.05  # known from simulation; could be inferred
        # Compute derivatives via finite difference
        dZ = np.gradient(self.latent_trajectory, dt, axis=0)  # (T, 2)
        # We'll use the first T-1 points for regression
        X = self.latent_trajectory[:-1, :]  # (T-1, 2)
        dX = dZ[:-1, :]  # (T-1, 2)

        # Build feature library: polynomial up to degree 3
        x = X[:, 0:1]
        y = X[:, 1:2]
        features = np.hstack([
            np.ones_like(x),           # 1
            x, y,
            x**2, x*y, y**2,
            x**3, (x**2)*y, x*(y**2), y**3
        ])  # shape (T-1, 10)

        # Fit Lasso for each derivative component
        lasso = Lasso(alpha=0.01, fit_intercept=False)
        coeffs = []
        for i in range(2):
            lasso.fit(features, dX[:, i:i+1].ravel())
            coeffs.append(lasso.coef_)

        # Identify active terms (coefficient magnitude > 1e-3)
        term_names = ['1', 'x', 'y', 'x^2', 'x*y', 'y^2', 'x^3', 'x^2*y', 'x*y^2', 'y^3']
        active_idx0 = np.where(np.abs(coeffs[0]) > 1e-3)[0]
        active_idx1 = np.where(np.abs(coeffs[1]) > 1e-3)[0]

        print("[SINDy] Discovered equations:")
        eq0 = "dx/dt = " + " + ".join(f"{coeffs[0][i]:.3f}*{term_names[i]}" for i in active_idx0)
        eq1 = "dy/dt = " + " + ".join(f"{coeffs[1][i]:.3f}*{term_names[i]}" for i in active_idx1)
        print(f"  {eq0}")
        print(f"  {eq1}")

        # Store as list of dicts for later use
        self.discovered_odes = [
            {"coeffs": coeffs[0][active_idx0], "terms": [term_names[i] for i in active_idx0]},
            {"coeffs": coeffs[1][active_idx1], "terms": [term_names[i] for i in active_idx1]}
        ]

    # -----------------------------------------------------------------
    # PHASE 4: VALIDATE via raw sensor reconstruction
    # -----------------------------------------------------------------
    def validate(self):
        """
        Integrate the discovered ODE from the initial latent state,
        project back to raw space using the decoder,
        and compute RMSE against the original raw data.
        """
        print("[VALIDATION] Testing discovered model...")
        # Initial latent state (first point)
        z0 = self.latent_trajectory[0, :]
        dt = 0.05
        T = self.latent_trajectory.shape[0]
        # Reconstruct latent trajectory using discovered ODE
        z_recon = [z0]
        for _ in range(T-1):
            z_curr = z_recon[-1]
            x, y = z_curr
            # Evaluate derivative using discovered coefficients
            # We'll compute using the full library and active coefficients
            # For simplicity, we evaluate both derivatives using the stored active terms
            # We'll use the full coefficient arrays (with zeros) for easier computation
            coeffs_full0 = np.zeros(10)
            coeffs_full1 = np.zeros(10)
            for idx, term in enumerate(self.discovered_odes[0]["terms"]):
                # map term to index in full library
                term_idx = ['1', 'x', 'y', 'x^2', 'x*y', 'y^2', 'x^3', 'x^2*y', 'x*y^2', 'y^3'].index(term)
                coeffs_full0[term_idx] = self.discovered_odes[0]["coeffs"][idx]
            for idx, term in enumerate(self.discovered_odes[1]["terms"]):
                term_idx = ['1', 'x', 'y', 'x^2', 'x*y', 'y^2', 'x^3', 'x^2*y', 'x*y^2', 'y^3'].index(term)
                coeffs_full1[term_idx] = self.discovered_odes[1]["coeffs"][idx]

            # Build feature vector for current state
            feats = np.array([1, x, y, x**2, x*y, y**2, x**3, (x**2)*y, x*(y**2), y**3])
            dxdt = np.dot(coeffs_full0, feats)
            dydt = np.dot(coeffs_full1, feats)
            z_next = z_curr + np.array([dxdt, dydt]) * dt
            z_recon.append(z_next)

        z_recon = np.array(z_recon)
        # Project back to raw space using the decoder
        with torch.no_grad():
            z_tensor = torch.tensor(z_recon, dtype=torch.float32)
            raw_recon = self.autoencoder.decoder(z_tensor).numpy()
        # Compute RMSE
        raw_actual = self.raw_data
        error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
        self.validation_error = error
        print(f"[VALIDATION] Raw sensor reconstruction RMSE: {error:.4f}")
        if error < 0.5:
            print("[PROMOTION] PASSED. Nonlinear latent dynamics validated.")
            print("[RESULT] AEGIS discovered a nonlinear ODE from raw data without labels.")
        else:
            print("[REJECTED] Reconstruction error too high.")

    # -----------------------------------------------------------------
    # RUN
    # -----------------------------------------------------------------
    def run(self):
        print("="*72)
        print("AEGIS V13 – NONLINEAR LATENT DYNAMICS DISCOVERY")
        print("Input: 5‑D raw sensor readings (nonlinear mixing).")
        print("Task: Discover 2‑D latent manifold and ODE.")
        print("="*72)
        self.train_autoencoder()
        self.discover_odes()
        self.validate()
        print("="*72)

# -----------------------------------------------------------------
# EXPERIMENT
# -----------------------------------------------------------------
def main():
    random.seed(42)
    np.random.seed(42)
    reality = HiddenRealityV13()
    data = []
    for _ in range(200):  # more steps for training
        data.append(reality.step(dt=0.05))
    agent = AEGIS_V13()
    agent.ingest(data)
    agent.run()

if __name__ == "__main__":
    main()
