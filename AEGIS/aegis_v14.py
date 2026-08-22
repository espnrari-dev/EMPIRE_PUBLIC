#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
import math
from typing import List, Tuple

# ============================================================
# AEGIS V14 – TRUE NONLINEAR PREDICTIVE VALIDATION
# ============================================================
#
# 1. Hidden Duffing oscillator.
# 2. Raw sensors are a nonlinear mixture (tanh).
# 3. Training = first 70% of timesteps.
# 4. Testing = last 30% (unseen during discovery).
# 5. AEGIS discovers latent ODE from training data.
# 6. Validation: integrate over the test window,
#    project to raw sensors, and compute RMSE.
# 7. PROMOTION granted ONLY if prediction error < 0.5.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (Duffing oscillator)
# -----------------------------------------------------------------
class HiddenRealityV14:
    def __init__(self):
        self.pos = 1.0
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
        # For storing the true hidden trajectory (for optional comparison)
        self.hidden_states = []

    def step(self, dt: float = 0.05) -> Tuple[List[float], List[float]]:
        # Duffing acceleration: x'' = -δ x' - α x - β x^3
        accel = -self.delta * self.vel - self.alpha * self.pos - self.beta * (self.pos**3)
        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1
        # Save hidden state for analysis (AEGIS never sees this)
        self.hidden_states.append([self.pos, self.vel])
        # Generate nonlinear raw sensors
        state = np.array([self.pos, self.vel])
        raw = np.tanh(self.M @ state + self.bias) + np.random.normal(0, 0.02, size=5)
        return raw.tolist(), [self.pos, self.vel]

# -----------------------------------------------------------------
# 2. AEGIS V14 ENGINE (Pure NumPy)
# -----------------------------------------------------------------
class AEGIS_V14:
    def __init__(self):
        self.train_raw = None
        self.test_raw = None
        self.train_latent = None
        self.test_latent_actual = None
        self.coeffs = None
        self.term_names = None
        self.projection_matrix = None
        self.prediction_error = None

    # -----------------------------------------------------------------
    # PHASE 1: INGEST AND SPLIT RAW DATA (unlabeled)
    # -----------------------------------------------------------------
    def ingest(self, raw_data: List[List[float]], split_ratio: float = 0.7):
        raw_data = np.array(raw_data, dtype=np.float64)
        n = len(raw_data)
        split_idx = int(n * split_ratio)
        self.train_raw = raw_data[:split_idx]
        self.test_raw = raw_data[split_idx:]
        print(f"[INGEST] Total steps: {n}")
        print(f"[INGEST] Training steps: {len(self.train_raw)}")
        print(f"[INGEST] Test steps (unseen): {len(self.test_raw)}")

    # -----------------------------------------------------------------
    # PHASE 2: DELAY EMBEDDING (Training phase)
    # -----------------------------------------------------------------
    def embed(self, delay: int = 1, dimension: int = 2):
        print("[EMBED] Reconstructing latent space from training sensors...")
        # Use the first raw sensor for embedding (could use PCA, but this is simplest)
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

        # We also need to align the test sensors to the same embedding window.
        # We'll extract the test latent states by using the same lag structure
        # from the test raw data.
        test_signal = self.test_raw[:, 0]
        test_embedded = []
        for i in range(max_idx):
            # We need to shift the test window relative to the training end.
            # Actually, for validation we will just predict forward from the last training point.
            # So we don't need a full test latent trajectory from embedding.
            # We'll just use the training latent trajectory to learn dynamics.
            pass

    # -----------------------------------------------------------------
    # PHASE 3: DISCOVER ODE via SINDy (Training phase)
    # -----------------------------------------------------------------
    def discover_ode(self, dt: float = 0.05, threshold: float = 0.05):
        print("[SINDy] Discovering ODE from latent training trajectory...")
        z = self.train_latent
        T, d = z.shape

        # Compute derivatives using finite differences
        dz = np.gradient(z, dt, axis=0)

        # Feature library: polynomial up to degree 3 (nonlinear Duffing needs cubic)
        x = z[:, 0:1]
        y = z[:, 1:2] if d >= 2 else np.zeros_like(x)
        features = np.hstack([
            np.ones_like(x),          # 1
            x, y,                     # x, y
            x**2, x*y, y**2,          # quadratic
            x**3, (x**2)*y, x*(y**2), y**3  # cubic
        ])
        self.term_names = ['1', 'x', 'y', 'x^2', 'xy', 'y^2', 'x^3', 'x^2 y', 'x y^2', 'y^3']

        # Sparse regression for each derivative component
        coeffs_list = []
        for k in range(d):
            target = dz[:, k]
            # Least squares
            coeffs = np.linalg.lstsq(features, target, rcond=None)[0]
            # Hard-thresholding
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

        # Display discovered equations
        print("[SINDy] Discovered equations on training data:")
        for k, coeffs in enumerate(coeffs_list):
            active = np.where(np.abs(coeffs) > 1e-6)[0]
            terms = [f"{coeffs[i]:.3f}*{self.term_names[i]}" for i in active]
            eq = f"dz{k+1}/dt = " + (" + ".join(terms) if terms else "0")
            print(f"  {eq}")

    # -----------------------------------------------------------------
    # PHASE 4: TRAIN SENSOR PROJECTION (Training phase)
    # -----------------------------------------------------------------
    def train_projection(self):
        """Learn linear mapping from latent trajectory to raw sensors."""
        print("[PROJECTION] Learning latent -> sensor mapping...")
        # We'll align the raw sensors to the available latent points
        n_points = len(self.train_latent)
        latent_train = self.train_latent
        raw_aligned = self.train_raw[:n_points]
        self.projection_matrix = np.linalg.lstsq(latent_train, raw_aligned, rcond=None)[0]
        # Check reconstruction on training data (just for sanity)
        raw_recon_train = latent_train @ self.projection_matrix
        train_error = np.sqrt(np.mean((raw_aligned - raw_recon_train)**2))
        print(f"[PROJECTION] Training reconstruction RMSE: {train_error:.4f}")

    # -----------------------------------------------------------------
    # PHASE 5: VALIDATE ON UNSEEN TEST WINDOW (Predictive validation)
    # -----------------------------------------------------------------
    def validate_predictive(self, dt: float = 0.05):
        """
        Start from the last training latent state.
        Integrate the discovered ODE forward over the entire test window.
        Project to raw sensors using the trained projection.
        Compare against the actual held-out test sensors.
        """
        print("[VALIDATION] Integrating discovered ODE over the UNSEEN test window...")
        # Initial condition: last point of training latent trajectory
        z0 = self.train_latent[-1, :]
        n_test = len(self.test_raw)

        # Reconstruct latent trajectory over the test window
        z_recon = [z0.copy()]
        for _ in range(n_test - 1):
            z_curr = z_recon[-1]
            x = z_curr[0]
            y = z_curr[1] if len(z_curr) > 1 else 0.0
            feats = np.array([1, x, y, x**2, x*y, y**2, x**3, (x**2)*y, x*(y**2), y**3])
            dz = np.zeros(len(z_curr))
            for k in range(len(z_curr)):
                dz[k] = np.dot(self.coeffs[k], feats)
            z_next = z_curr + dz * dt
            z_recon.append(z_next)

        z_recon = np.asarray(z_recon)
        # Project reconstructed latent states to raw sensors
        raw_recon = z_recon @ self.projection_matrix

        # Compute prediction error on the held-out test set
        raw_actual = self.test_raw
        error = np.sqrt(np.mean((raw_actual - raw_recon)**2))
        self.prediction_error = error
        print(f"[VALIDATION] Held-out test sensor RMSE: {error:.4f}")

        # PROMOTION GATE
        if error < 0.5:
            print("[PROMOTION] PASSED. The discovered ODE successfully predicts the unseen test window.")
            print("[RESULT] AEGIS has discovered a valid nonlinear dynamical system from raw data.")
        else:
            print("[REJECTED] Prediction error too high. The discovered dynamics do not generalize.")

    # -----------------------------------------------------------------
    # OPTIONAL: COMPARE TO TRUE HIDDEN DYNAMICS (for analysis only)
    # -----------------------------------------------------------------
    def compare_to_true(self, true_hidden_trajectory, dt: float = 0.05):
        """
        Since the latent coordinates are arbitrary (delay embedding),
        we cannot directly compare coefficients. But we can check if
        the qualitative behavior matches (e.g., limit cycle).
        This is just for informational purposes.
        """
        print("\n[ANALYSIS] Comparing discovered latent dynamics to true hidden states...")
        print("Note: Latent coordinates are arbitrary delay coordinates.")
        print("SINDy finds a *diffeomorphic* transformation of the true dynamics.")
        print("Qualitative match is expected if prediction error is low.")

# -----------------------------------------------------------------
# 6. EXPERIMENT
# -----------------------------------------------------------------
def main():
    random.seed(42)
    np.random.seed(42)

    # Generate data
    reality = HiddenRealityV14()
    raw_data = []
    hidden_states = []
    for _ in range(300):  # Total steps
        raw, hidden = reality.step(dt=0.05)
        raw_data.append(raw)
        hidden_states.append(hidden)

    # AEGIS engine
    agent = AEGIS_V14()
    agent.ingest(raw_data, split_ratio=0.7)  # First 70% training, last 30% test

    print("="*72)
    print("AEGIS V14 – TRUE NONLINEAR PREDICTIVE DISCOVERY")
    print("="*72)

    # Step 1: Embedding (latent space discovery)
    agent.embed(delay=1, dimension=2)

    # Step 2: Discover ODE (SINDy on training latent trajectory)
    agent.discover_ode(dt=0.05, threshold=0.05)

    # Step 3: Train sensor projection (latent -> raw)
    agent.train_projection()

    # Step 4: Validate on unseen test window
    agent.validate_predictive(dt=0.05)

    print("="*72)

if __name__ == "__main__":
    main()
