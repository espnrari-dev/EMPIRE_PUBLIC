#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
from typing import List, Tuple


# ============================================================
# AEGIS V17 — DIRECT HELD-OUT IDENTIFIABILITY
# ============================================================
#
# V17 closes the remaining V16 gap.
#
# V16:
#   learned ODE -> predicted latent test trajectory
#   -> hidden-state comparison
#
# V17:
#   raw held-out observations
#   -> discovered latent representation directly
#   -> training-only affine mapping
#   -> hidden-state prediction on unseen observations
#
# Hidden state is NEVER used to construct the latent space.
# Hidden state is used ONLY for evaluation.
#
# Two separate evaluations are reported:
#
#   1. DIRECT IDENTIFIABILITY
#      Does the discovered representation map to the
#      hidden physical state on unseen observations?
#
#   2. DYNAMICAL IDENTIFIABILITY
#      Does the learned discovered ODE preserve that
#      relationship when rolled forward?
#
# ============================================================


class HiddenRealityV17:

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
        ], dtype=np.float64)

        self.bias = np.array([
            0.2,
            -0.1,
            0.3,
            -0.2,
            0.1
        ], dtype=np.float64)

        self.time = 0
        self.hidden_states = []

    def step(
        self,
        dt: float = 0.05
    ) -> Tuple[List[float], List[float]]:

        accel = (
            -self.delta * self.vel
            - self.alpha * self.pos
            - self.beta * (self.pos ** 3)
        )

        self.vel += accel * dt
        self.pos += self.vel * dt
        self.time += 1

        hidden = [self.pos, self.vel]
        self.hidden_states.append(hidden)

        state = np.array(
            [self.pos, self.vel],
            dtype=np.float64
        )

        raw = (
            np.tanh(self.M @ state + self.bias)
            + np.random.normal(
                0,
                0.02,
                size=5
            )
        )

        return raw.tolist(), hidden


class AEGIS_V17:

    def __init__(self):

        self.train_raw = None
        self.test_raw = None

        self.train_latent = None
        self.test_latent = None

        self.train_latent_norm = None

        self.latent_mean = None
        self.latent_std = None

        self.coeffs = None
        self.projection_matrix = None

        self.hidden_states_train = None
        self.hidden_states_test = None

    # ========================================================
    # INGEST
    # ========================================================

    def ingest(
        self,
        raw_data: List[List[float]],
        hidden_data: List[List[float]],
        split_ratio: float = 0.7
    ):

        raw_data = np.asarray(
            raw_data,
            dtype=np.float64
        )

        hidden_data = np.asarray(
            hidden_data,
            dtype=np.float64
        )

        if len(raw_data) != len(hidden_data):
            raise ValueError(
                "Raw and hidden data lengths differ."
            )

        n = len(raw_data)
        split_idx = int(n * split_ratio)

        self.train_raw = raw_data[:split_idx]
        self.test_raw = raw_data[split_idx:]

        self.hidden_states_train = hidden_data[:split_idx]
        self.hidden_states_test = hidden_data[split_idx:]

        print(
            f"[INGEST] Train: {len(self.train_raw)}, "
            f"Test: {len(self.test_raw)}"
        )

    # ========================================================
    # LATENT EMBEDDING
    # ========================================================

    @staticmethod
    def build_embedding(
        raw_data: np.ndarray,
        delay: int = 1,
        dimension: int = 2
    ):

        signal = raw_data[:, 0]

        max_idx = len(signal) - (
            (dimension - 1) * delay
        )

        embedded = []

        for i in range(max_idx):

            vec = [
                signal[
                    i + j * delay
                ]
                for j in range(dimension)
            ]

            embedded.append(vec)

        return np.asarray(
            embedded,
            dtype=np.float64
        )

    def embed(
        self,
        delay: int = 1,
        dimension: int = 2
    ):

        self.train_latent = self.build_embedding(
            self.train_raw,
            delay,
            dimension
        )

        self.test_latent = self.build_embedding(
            self.test_raw,
            delay,
            dimension
        )

        self.latent_mean = np.mean(
            self.train_latent,
            axis=0
        )

        self.latent_std = (
            np.std(
                self.train_latent,
                axis=0
            )
            + 1e-8
        )

        self.train_latent_norm = (
            self.train_latent
            - self.latent_mean
        ) / self.latent_std

        print(
            f"[EMBED] Train latent: "
            f"{self.train_latent.shape}"
        )

        print(
            f"[EMBED] Test latent: "
            f"{self.test_latent.shape}"
        )

    # ========================================================
    # SINDy DISCOVERY
    # ========================================================

    def discover_ode(
        self,
        dt: float = 0.05,
        threshold: float = 0.05
    ):

        z = self.train_latent_norm

        dz = np.gradient(
            z,
            dt,
            axis=0
        )

        x = z[:, 0:1]
        y = z[:, 1:2]

        features = np.hstack([
            np.ones_like(x),
            x,
            y,
            x ** 2,
            x * y,
            y ** 2
        ])

        term_names = [
            "1",
            "x",
            "y",
            "x^2",
            "xy",
            "y^2"
        ]

        coeffs_list = []

        for k in range(z.shape[1]):

            target = dz[:, k]

            coeffs = np.linalg.lstsq(
                features,
                target,
                rcond=None
            )[0]

            for _ in range(5):

                small = (
                    np.abs(coeffs)
                    < threshold
                )

                coeffs[small] = 0.0

                if not np.any(~small):
                    break

                active = ~small

                coeffs[active] = np.linalg.lstsq(
                    features[:, active],
                    target,
                    rcond=None
                )[0]

            coeffs_list.append(coeffs)

        self.coeffs = coeffs_list

        print("[SINDy] Equations (normalized):")

        for k, c in enumerate(coeffs_list):

            active = np.where(
                np.abs(c) > 1e-6
            )[0]

            terms = [
                f"{c[i]:.3f}*{term_names[i]}"
                for i in active
            ]

            print(
                f"  dz{k + 1}/dt = "
                + " + ".join(terms)
            )

    # ========================================================
    # SENSOR PROJECTION
    # ========================================================

    def train_projection(self):

        n = len(self.train_latent)

        raw_aligned = self.train_raw[:n]

        self.projection_matrix = np.linalg.lstsq(
            self.train_latent_norm,
            raw_aligned,
            rcond=None
        )[0]

        recon = (
            self.train_latent_norm
            @ self.projection_matrix
        )

        rmse = np.sqrt(
            np.mean(
                (raw_aligned - recon) ** 2
            )
        )

        print(
            f"[PROJECTION] Train recon RMSE: "
            f"{rmse:.6f}"
        )

        return rmse

    # ========================================================
    # ODE INTEGRATION
    # ========================================================

    def derivative(self, z):

        x = z[0]
        y = z[1]

        features = np.array([
            1.0,
            x,
            y,
            x ** 2,
            x * y,
            y ** 2
        ])

        return np.array([
            np.dot(
                self.coeffs[0],
                features
            ),
            np.dot(
                self.coeffs[1],
                features
            )
        ])

    def integrate(
        self,
        z0_norm,
        n_steps,
        dt=0.05
    ):

        z = np.asarray(
            z0_norm,
            dtype=np.float64
        ).copy()

        traj = [z.copy()]

        for _ in range(n_steps - 1):

            z_curr = traj[-1]

            k1 = self.derivative(z_curr)

            k2 = self.derivative(
                z_curr
                + 0.5 * dt * k1
            )

            k3 = self.derivative(
                z_curr
                + 0.5 * dt * k2
            )

            k4 = self.derivative(
                z_curr
                + dt * k3
            )

            z_next = (
                z_curr
                + (dt / 6.0)
                * (
                    k1
                    + 2 * k2
                    + 2 * k3
                    + k4
                )
            )

            traj.append(z_next)

        return np.asarray(traj)

    # ========================================================
    # DIRECT IDENTIFIABILITY
    # ========================================================

    def direct_identifiability(self):

        print("\n" + "=" * 72)
        print(
            "[DIRECT IDENTIFIABILITY] "
            "Unseen observations -> hidden state"
        )
        print("=" * 72)

        # ----------------------------------------------------
        # IMPORTANT:
        # Hidden state is NOT used to construct the test
        # representation.
        #
        # The test latent representation comes directly
        # from unseen raw observations.
        # ----------------------------------------------------

        train_latent = self.train_latent

        test_latent = self.test_latent

        n_train = len(train_latent)
        n_test = len(test_latent)

        hidden_train = self.hidden_states_train[
            :n_train
        ]

        hidden_test = self.hidden_states_test[
            :n_test
        ]

        # ----------------------------------------------------
        # Fit mapping ONLY on training data.
        # ----------------------------------------------------

        train_aug = np.hstack([
            train_latent,
            np.ones(
                (n_train, 1)
            )
        ])

        W = np.linalg.lstsq(
            train_aug,
            hidden_train,
            rcond=None
        )[0]

        # ----------------------------------------------------
        # Apply untouched mapping to test representation.
        # ----------------------------------------------------

        test_aug = np.hstack([
            test_latent,
            np.ones(
                (n_test, 1)
            )
        ])

        hidden_pred = test_aug @ W

        error = np.sqrt(
            np.mean(
                (
                    hidden_test
                    - hidden_pred
                ) ** 2
            )
        )

        print(
            f"[DIRECT IDENTIFIABILITY] "
            f"Test hidden-state RMSE: {error:.9f}"
        )

        # ----------------------------------------------------
        # Safe correlation.
        # ----------------------------------------------------

        def safe_corr(a, b):

            a = np.asarray(a)
            b = np.asarray(b)

            a_std = np.std(a)
            b_std = np.std(b)

            eps = 1e-12

            if (
                a_std <= eps
                or b_std <= eps
            ):
                return np.nan

            return float(
                np.corrcoef(a, b)[0, 1]
            )

        corr_pos = safe_corr(
            hidden_test[:, 0],
            hidden_pred[:, 0]
        )

        corr_vel = safe_corr(
            hidden_test[:, 1],
            hidden_pred[:, 1]
        )

        if np.isnan(corr_pos):
            print(
                "[DIRECT IDENTIFIABILITY] "
                "Correlation (pos): undefined "
                "(constant series)"
            )
        else:
            print(
                f"[DIRECT IDENTIFIABILITY] "
                f"Correlation (pos): {corr_pos:.9f}"
            )

        if np.isnan(corr_vel):
            print(
                "[DIRECT IDENTIFIABILITY] "
                "Correlation (vel): undefined "
                "(constant series)"
            )
        else:
            print(
                f"[DIRECT IDENTIFIABILITY] "
                f"Correlation (vel): {corr_vel:.9f}"
            )

        strong = (
            error < 0.2
            and (
                np.isnan(corr_pos)
                or corr_pos > 0.95
            )
            and (
                np.isnan(corr_vel)
                or corr_vel > 0.95
            )
        )

        if strong:

            print(
                "[RESULT] STRONG DIRECT "
                "IDENTIFIABILITY"
            )

            print(
                "[RESULT] The discovered representation "
                "recovers the hidden state on unseen "
                "observations using a mapping learned "
                "only from training data."
            )

        else:

            print(
                "[RESULT] DIRECT IDENTIFIABILITY "
                "NOT YET STRONG"
            )

        return {
            "rmse": error,
            "corr_pos": corr_pos,
            "corr_vel": corr_vel,
            "strong": strong
        }

    # ========================================================
    # DYNAMICAL IDENTIFIABILITY
    # ========================================================

    def dynamical_identifiability(
        self,
        dt=0.05
    ):

        print("\n" + "=" * 72)
        print(
            "[DYNAMICAL IDENTIFIABILITY] "
            "Learned ODE rollout -> hidden state"
        )
        print("=" * 72)

        z0_norm = (
            self.train_latent[-1]
            - self.latent_mean
        ) / self.latent_std

        n_test = len(
            self.test_latent
        )

        rollout_norm = self.integrate(
            z0_norm,
            n_test,
            dt
        )

        rollout = (
            rollout_norm
            * self.latent_std
            + self.latent_mean
        )

        # Fit affine mapping on training latent state.
        n_train = len(
            self.train_latent
        )

        train_aug = np.hstack([
            self.train_latent,
            np.ones(
                (n_train, 1)
            )
        ])

        hidden_train = (
            self.hidden_states_train[
                :n_train
            ]
        )

        W = np.linalg.lstsq(
            train_aug,
            hidden_train,
            rcond=None
        )[0]

        rollout_aug = np.hstack([
            rollout,
            np.ones(
                (len(rollout), 1)
            )
        ])

        hidden_pred = (
            rollout_aug @ W
        )

        hidden_actual = (
            self.hidden_states_test[
                :len(rollout)
            ]
        )

        error = np.sqrt(
            np.mean(
                (
                    hidden_actual
                    - hidden_pred
                ) ** 2
            )
        )

        print(
            f"[DYNAMICAL IDENTIFIABILITY] "
            f"Rollout hidden-state RMSE: "
            f"{error:.9f}"
        )

        return error

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_predictive(
        self,
        dt=0.05
    ):

        z0_norm = (
            self.train_latent[-1]
            - self.latent_mean
        ) / self.latent_std

        n_test = len(
            self.test_raw
        )

        z_recon_norm = self.integrate(
            z0_norm,
            n_test,
            dt
        )

        raw_recon = (
            z_recon_norm
            @ self.projection_matrix
        )

        # Align lengths.
        n = min(
            len(self.test_raw),
            len(raw_recon)
        )

        error = np.sqrt(
            np.mean(
                (
                    self.test_raw[:n]
                    - raw_recon[:n]
                ) ** 2
            )
        )

        print(
            f"[VALIDATION] Held-out sensor RMSE: "
            f"{error:.6f}"
        )

        return error


# ============================================================
# MAIN
# ============================================================

def main():

    random.seed(42)
    np.random.seed(42)

    reality = HiddenRealityV17()

    raw_data = []
    hidden_data = []

    for _ in range(300):

        raw, hidden = reality.step(
            dt=0.05
        )

        raw_data.append(raw)
        hidden_data.append(hidden)

    agent = AEGIS_V17()

    agent.ingest(
        raw_data,
        hidden_data,
        split_ratio=0.7
    )

    print("=" * 72)
    print(
        "AEGIS V17 – DIRECT HELD-OUT IDENTIFIABILITY"
    )
    print("=" * 72)

    agent.embed(
        delay=1,
        dimension=2
    )

    agent.discover_ode(
        dt=0.05,
        threshold=0.05
    )

    agent.train_projection()

    agent.validate_predictive(
        dt=0.05
    )

    direct = agent.direct_identifiability()

    dynamic = agent.dynamical_identifiability(
        dt=0.05
    )

    print("\n" + "=" * 72)
    print("AEGIS V17 SUMMARY")
    print("=" * 72)

    print(
        f"Direct identifiability RMSE: "
        f"{direct['rmse']:.9f}"
    )

    print(
        f"Dynamical identifiability RMSE: "
        f"{dynamic:.9f}"
    )

    if direct["strong"]:

        print(
            "[V17 STATUS] FORWARD"
        )

        print(
            "[V17 STATUS] Direct held-out "
            "identifiability established."
        )

        print(
            "[V17 STATUS] The discovered "
            "representation itself, rather than "
            "only its learned rollout, has now "
            "been tested against unseen data."
        )

    else:

        print(
            "[V17 STATUS] GAP REMAINS"
        )

        print(
            "[V17 STATUS] Direct held-out "
            "identifiability requires improvement."
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
