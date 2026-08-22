#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
from typing import List, Tuple


# ============================================================
# AEGIS V18 — RIGOROUS IDENTIFIABILITY
# ============================================================
#
# PURPOSE
# -------
# Establish whether a discovered representation contains
# sufficient information to recover a nontrivial hidden
# physical state on genuinely unseen trajectories.
#
# V18 explicitly prevents:
#
#   - equilibrium / constant-state false positives
#   - train/test temporal leakage
#   - hidden-state leakage into representation discovery
#   - invalid correlation promotion
#   - single-trajectory conclusions
#   - unsupported "exact linear transformation" claims
#
# EXPERIMENT
# ----------
#
# Hidden physical state:
#
#       state = [position, velocity]
#
# Sensor:
#
#       raw = tanh(M @ state + bias) + noise
#
# Discovery sees ONLY raw sensor observations.
#
# Hidden state is used ONLY after discovery for evaluation.
#
# TRAIN:
#   multiple independent trajectories
#
# TEST:
#   completely separate trajectories
#
# IDENTIFIABILITY:
#   discovered representation -> hidden state
#
# Two mappings are evaluated:
#
#   1. AFFINE
#      Tests the strong claim that the representation is
#      linearly/affinely equivalent to the hidden state.
#
#   2. POLYNOMIAL
#      Tests whether a smooth nonlinear coordinate mapping
#      can recover the hidden state.
#
# The distinction matters:
#
#   affine success = strong coordinate equivalence
#   nonlinear success = information-preserving nonlinear
#                     representation
#
# V18 will NOT call nonlinear success "linear identifiability".
#
# ============================================================


class HiddenRealityV18:

    def __init__(self, seed: int):

        self.rng = np.random.default_rng(seed)

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

    def rollout(
        self,
        pos0: float,
        vel0: float,
        steps: int = 160,
        dt: float = 0.05
    ) -> Tuple[np.ndarray, np.ndarray]:

        pos = float(pos0)
        vel = float(vel0)

        raw_data = []
        hidden_data = []

        for _ in range(steps):

            accel = (
                -self.delta * vel
                - self.alpha * pos
                - self.beta * (pos ** 3)
            )

            vel += accel * dt
            pos += vel * dt

            state = np.array(
                [pos, vel],
                dtype=np.float64
            )

            raw = (
                np.tanh(
                    self.M @ state + self.bias
                )
                + self.rng.normal(
                    0.0,
                    0.02,
                    size=5
                )
            )

            raw_data.append(raw)
            hidden_data.append(state)

        return (
            np.asarray(raw_data),
            np.asarray(hidden_data)
        )


# ============================================================
# DATASET
# ============================================================

def make_dataset(
    seed: int,
    n_train: int = 8,
    n_test: int = 4,
    steps: int = 160
):

    rng = np.random.default_rng(seed)

    reality = HiddenRealityV18(seed)

    train_raw = []
    train_hidden = []

    test_raw = []
    test_hidden = []

    # --------------------------------------------------------
    # Independent initial conditions.
    #
    # These deliberately avoid the old equilibrium:
    #
    # pos = 1.0, vel = 0.0
    #
    # --------------------------------------------------------

    for _ in range(n_train):

        pos0 = rng.uniform(
            -0.8,
            0.8
        )

        vel0 = rng.uniform(
            -0.8,
            0.8
        )

        # Reject near-equilibrium starts.
        if abs(pos0 - 1.0) < 0.05 and abs(vel0) < 0.05:
            pos0 = 0.35
            vel0 = 0.55

        raw, hidden = reality.rollout(
            pos0,
            vel0,
            steps=steps
        )

        train_raw.append(raw)
        train_hidden.append(hidden)

    for _ in range(n_test):

        pos0 = rng.uniform(
            -0.8,
            0.8
        )

        vel0 = rng.uniform(
            -0.8,
            0.8
        )

        if abs(pos0 - 1.0) < 0.05 and abs(vel0) < 0.05:
            pos0 = -0.45
            vel0 = 0.60

        raw, hidden = reality.rollout(
            pos0,
            vel0,
            steps=steps
        )

        test_raw.append(raw)
        test_hidden.append(hidden)

    return (
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    )


# ============================================================
# AEGIS
# ============================================================

class AEGIS_V18:

    def __init__(self):

        self.train_raw = None
        self.test_raw = None

        self.train_hidden = None
        self.test_hidden = None

        self.train_latent = None
        self.test_latent = None

        self.latent_mean = None
        self.latent_std = None

        self.coeffs = None

    # ========================================================
    # INGEST
    # ========================================================

    def ingest(
        self,
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    ):

        self.train_raw = np.asarray(
            train_raw,
            dtype=np.float64
        )

        self.test_raw = np.asarray(
            test_raw,
            dtype=np.float64
        )

        self.train_hidden = np.asarray(
            train_hidden,
            dtype=np.float64
        )

        self.test_hidden = np.asarray(
            test_hidden,
            dtype=np.float64
        )

        print(
            f"[INGEST] Training trajectories: "
            f"{len(train_raw)}"
        )

        print(
            f"[INGEST] Test trajectories: "
            f"{len(test_raw)}"
        )

    # ========================================================
    # EMBEDDING
    # ========================================================

    @staticmethod
    def embed_trajectory(
        raw,
        delay=1,
        dimension=2
    ):

        signal = raw[:, 0]

        n = len(signal) - (
            (dimension - 1) * delay
        )

        embedded = []

        for i in range(n):

            embedded.append([
                signal[
                    i + j * delay
                ]
                for j in range(dimension)
            ])

        return np.asarray(
            embedded,
            dtype=np.float64
        )

    def embed_all(
        self,
        delay=1,
        dimension=2
    ):

        self.train_latent = [
            self.embed_trajectory(
                x,
                delay,
                dimension
            )
            for x in self.train_raw
        ]

        self.test_latent = [
            self.embed_trajectory(
                x,
                delay,
                dimension
            )
            for x in self.test_raw
        ]

        all_train = np.vstack(
            self.train_latent
        )

        self.latent_mean = np.mean(
            all_train,
            axis=0
        )

        self.latent_std = (
            np.std(
                all_train,
                axis=0
            )
            + 1e-8
        )

        self.train_latent = [
            (
                z
                - self.latent_mean
            ) / self.latent_std
            for z in self.train_latent
        ]

        self.test_latent = [
            (
                z
                - self.latent_mean
            ) / self.latent_std
            for z in self.test_latent
        ]

        print(
            "[EMBED] Representation generated "
            "without hidden-state access."
        )

    # ========================================================
    # DISCOVER ODE
    # ========================================================

    def discover_ode(
        self,
        dt=0.05,
        threshold=0.05
    ):

        z = np.vstack(
            self.train_latent
        )

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

        names = [
            "1",
            "x",
            "y",
            "x^2",
            "xy",
            "y^2"
        ]

        coeffs = []

        for k in range(
            z.shape[1]
        ):

            target = dz[:, k]

            c = np.linalg.lstsq(
                features,
                target,
                rcond=None
            )[0]

            for _ in range(8):

                small = (
                    np.abs(c)
                    < threshold
                )

                if np.all(small):
                    c[:] = 0.0
                    break

                active = ~small

                c[small] = 0.0

                c[active] = np.linalg.lstsq(
                    features[:, active],
                    target,
                    rcond=None
                )[0]

            coeffs.append(c)

        self.coeffs = coeffs

        print(
            "[SINDy] Discovered normalized equations:"
        )

        for k, c in enumerate(coeffs):

            active = np.where(
                np.abs(c) > 1e-6
            )[0]

            if len(active) == 0:

                print(
                    f"  dz{k+1}/dt = 0"
                )

                continue

            equation = " + ".join(
                f"{c[i]:.3f}*{names[i]}"
                for i in active
            )

            print(
                f"  dz{k+1}/dt = {equation}"
            )

    # ========================================================
    # ALIGNMENT
    # ========================================================

    @staticmethod
    def aligned_hidden(
        hidden,
        dimension=2,
        delay=1
    ):

        n = len(hidden) - (
            (dimension - 1) * delay
        )

        return hidden[:n]

    # ========================================================
    # VARIANCE GATE
    # ========================================================

    @staticmethod
    def variance_report(
        hidden,
        label
    ):

        std = np.std(
            hidden,
            axis=0
        )

        print(
            f"[VARIANCE] {label} "
            f"position std={std[0]:.9f}, "
            f"velocity std={std[1]:.9f}"
        )

        return std

    # ========================================================
    # AFFINE MAPPING
    # ========================================================

    @staticmethod
    def affine_fit_predict(
        train_z,
        train_hidden,
        test_z
    ):

        train_aug = np.hstack([
            train_z,
            np.ones(
                (len(train_z), 1)
            )
        ])

        W = np.linalg.lstsq(
            train_aug,
            train_hidden,
            rcond=None
        )[0]

        test_aug = np.hstack([
            test_z,
            np.ones(
                (len(test_z), 1)
            )
        ])

        return (
            test_aug @ W
        )

    # ========================================================
    # POLYNOMIAL MAPPING
    # ========================================================

    @staticmethod
    def poly_features(z):

        x = z[:, 0]
        y = z[:, 1]

        return np.column_stack([
            np.ones(len(z)),
            x,
            y,
            x * x,
            x * y,
            y * y
        ])

    @classmethod
    def polynomial_fit_predict(
        cls,
        train_z,
        train_hidden,
        test_z
    ):

        A = cls.poly_features(
            train_z
        )

        B = cls.poly_features(
            test_z
        )

        W = np.linalg.lstsq(
            A,
            train_hidden,
            rcond=None
        )[0]

        return B @ W

    # ========================================================
    # RMSE
    # ========================================================

    @staticmethod
    def rmse(
        actual,
        predicted
    ):

        return float(
            np.sqrt(
                np.mean(
                    (
                        actual
                        - predicted
                    ) ** 2
                )
            )
        )

    # ========================================================
    # SAFE CORRELATION
    # ========================================================

    @staticmethod
    def correlation(
        actual,
        predicted
    ):

        a = np.asarray(actual)
        b = np.asarray(predicted)

        if (
            np.std(a) < 1e-10
            or np.std(b) < 1e-10
        ):
            return np.nan

        return float(
            np.corrcoef(
                a,
                b
            )[0, 1]
        )

    # ========================================================
    # DIRECT IDENTIFIABILITY
    # ========================================================

    def direct_identifiability(self):

        print("\n" + "=" * 72)
        print(
            "[DIRECT IDENTIFIABILITY]"
        )
        print(
            "Independent unseen trajectories"
        )
        print("=" * 72)

        train_z = np.vstack(
            self.train_latent
        )

        test_z = np.vstack(
            self.test_latent
        )

        train_h = np.vstack([
            self.aligned_hidden(
                h
            )
            for h in self.train_hidden
        ])

        test_h = np.vstack([
            self.aligned_hidden(
                h
            )
            for h in self.test_hidden
        ])

        train_std = self.variance_report(
            train_h,
            "TRAIN HIDDEN"
        )

        test_std = self.variance_report(
            test_h,
            "TEST HIDDEN"
        )

        if np.any(
            train_std < 1e-5
        ):

            raise RuntimeError(
                "FAIL: Training hidden state "
                "is degenerate."
            )

        if np.any(
            test_std < 1e-5
        ):

            raise RuntimeError(
                "FAIL: Test hidden state "
                "is degenerate."
            )

        # ----------------------------------------------------
        # Affine mapping
        # ----------------------------------------------------

        affine_pred = (
            self.affine_fit_predict(
                train_z,
                train_h,
                test_z
            )
        )

        affine_error = self.rmse(
            test_h,
            affine_pred
        )

        affine_pos = self.correlation(
            test_h[:, 0],
            affine_pred[:, 0]
        )

        affine_vel = self.correlation(
            test_h[:, 1],
            affine_pred[:, 1]
        )

        print(
            f"[AFFINE] Test RMSE: "
            f"{affine_error:.9f}"
        )

        print(
            f"[AFFINE] Position correlation: "
            f"{affine_pos:.9f}"
        )

        print(
            f"[AFFINE] Velocity correlation: "
            f"{affine_vel:.9f}"
        )

        # ----------------------------------------------------
        # Polynomial mapping
        # ----------------------------------------------------

        poly_pred = (
            self.polynomial_fit_predict(
                train_z,
                train_h,
                test_z
            )
        )

        poly_error = self.rmse(
            test_h,
            poly_pred
        )

        poly_pos = self.correlation(
            test_h[:, 0],
            poly_pred[:, 0]
        )

        poly_vel = self.correlation(
            test_h[:, 1],
            poly_pred[:, 1]
        )

        print(
            f"[POLYNOMIAL] Test RMSE: "
            f"{poly_error:.9f}"
        )

        print(
            f"[POLYNOMIAL] Position correlation: "
            f"{poly_pos:.9f}"
        )

        print(
            f"[POLYNOMIAL] Velocity correlation: "
            f"{poly_vel:.9f}"
        )

        # ----------------------------------------------------
        # Baseline
        # ----------------------------------------------------

        baseline = np.mean(
            train_h,
            axis=0
        )

        baseline_pred = np.tile(
            baseline,
            (len(test_h), 1)
        )

        baseline_error = self.rmse(
            test_h,
            baseline_pred
        )

        print(
            f"[BASELINE] Constant-state RMSE: "
            f"{baseline_error:.9f}"
        )

        # ----------------------------------------------------
        # Improvement over baseline
        # ----------------------------------------------------

        affine_improvement = (
            1.0
            - affine_error
            / max(
                baseline_error,
                1e-12
            )
        )

        poly_improvement = (
            1.0
            - poly_error
            / max(
                baseline_error,
                1e-12
            )
        )

        print(
            f"[AFFINE] Improvement over baseline: "
            f"{affine_improvement * 100:.3f}%"
        )

        print(
            f"[POLYNOMIAL] Improvement over baseline: "
            f"{poly_improvement * 100:.3f}%"
        )

        # ----------------------------------------------------
        # Classification
        # ----------------------------------------------------

        affine_strong = (
            affine_error < 0.10
            and affine_pos > 0.95
            and affine_vel > 0.95
            and affine_improvement > 0.90
        )

        nonlinear_strong = (
            poly_error < 0.10
            and poly_pos > 0.95
            and poly_vel > 0.95
            and poly_improvement > 0.90
        )

        if affine_strong:

            result = (
                "STRONG AFFINE IDENTIFIABILITY"
            )

        elif nonlinear_strong:

            result = (
                "STRONG NONLINEAR "
                "IDENTIFIABILITY"
            )

        else:

            result = (
                "IDENTIFIABILITY NOT "
                "YET ESTABLISHED"
            )

        print(
            f"[RESULT] {result}"
        )

        return {
            "affine_rmse": affine_error,
            "affine_pos": affine_pos,
            "affine_vel": affine_vel,
            "affine_improvement": affine_improvement,
            "poly_rmse": poly_error,
            "poly_pos": poly_pos,
            "poly_vel": poly_vel,
            "poly_improvement": poly_improvement,
            "baseline_rmse": baseline_error,
            "affine_strong": affine_strong,
            "nonlinear_strong": nonlinear_strong
        }


# ============================================================
# REPEATED TRIAL VALIDATION
# ============================================================

def run_trial(
    seed
):

    print("\n")
    print("#" * 72)
    print(
        f"AEGIS V18 TRIAL {seed}"
    )
    print("#" * 72)

    (
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    ) = make_dataset(
        seed=seed
    )

    agent = AEGIS_V18()

    agent.ingest(
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    )

    agent.embed_all(
        delay=1,
        dimension=2
    )

    agent.discover_ode(
        dt=0.05,
        threshold=0.05
    )

    return agent.direct_identifiability()


# ============================================================
# MAIN
# ============================================================

def main():

    random.seed(42)
    np.random.seed(42)

    print("=" * 72)
    print(
        "AEGIS V18 — RIGOROUS IDENTIFIABILITY"
    )
    print("=" * 72)

    results = []

    seeds = [
        42,
        43,
        44,
        45,
        46
    ]

    for seed in seeds:

        try:

            result = run_trial(
                seed
            )

            results.append(
                result
            )

        except Exception as exc:

            print(
                f"[TRIAL {seed}] FAIL: "
                f"{exc}"
            )

    print("\n" + "=" * 72)
    print(
        "AEGIS V18 FINAL AUDIT"
    )
    print("=" * 72)

    if not results:

        print(
            "[FINAL] FAIL — no valid trials."
        )

        return

    affine_passes = sum(
        r["affine_strong"]
        for r in results
    )

    nonlinear_passes = sum(
        r["nonlinear_strong"]
        for r in results
    )

    affine_errors = np.array([
        r["affine_rmse"]
        for r in results
    ])

    poly_errors = np.array([
        r["poly_rmse"]
        for r in results
    ])

    print(
        f"[FINAL] Valid trials: "
        f"{len(results)}/5"
    )

    print(
        f"[FINAL] Affine passes: "
        f"{affine_passes}/5"
    )

    print(
        f"[FINAL] Nonlinear passes: "
        f"{nonlinear_passes}/5"
    )

    print(
        f"[FINAL] Mean affine RMSE: "
        f"{np.mean(affine_errors):.9f}"
    )

    print(
        f"[FINAL] Mean nonlinear RMSE: "
        f"{np.mean(poly_errors):.9f}"
    )

    # --------------------------------------------------------
    # Strongest possible result from THIS experiment.
    #
    # All five independent trials must pass.
    # --------------------------------------------------------

    if (
        len(results) == 5
        and affine_passes == 5
    ):

        print(
            "[FINAL RESULT] "
            "STRONG AFFINE IDENTIFIABILITY"
        )

        print(
            "[FINAL RESULT] "
            "The discovered representation "
            "is consistently affinely equivalent "
            "to the hidden physical state across "
            "independent unseen trajectories."
        )

    elif (
        len(results) == 5
        and nonlinear_passes == 5
    ):

        print(
            "[FINAL RESULT] "
            "STRONG NONLINEAR IDENTIFIABILITY"
        )

        print(
            "[FINAL RESULT] "
            "The discovered representation "
            "consistently preserves the hidden "
            "state through a nonlinear coordinate "
            "mapping across independent unseen "
            "trajectories."
        )

        print(
            "[FINAL RESULT] "
            "Affine equivalence has NOT been "
            "claimed."
        )

    else:

        print(
            "[FINAL RESULT] "
            "IDENTIFIABILITY NOT YET ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The experiment correctly rejected "
            "a premature promotion."
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
