#!/data/data/com.termux/files/usr/bin/python

import random
import math
import numpy as np
from typing import Tuple


# ============================================================
# AEGIS V20 — IDENTIFIABILITY + STABLE DYNAMICAL AUDIT
# ============================================================
#
# PURPOSE
# -------
# Determine whether a hidden physical dynamical system can be
# reconstructed from sensor observations alone.
#
# HIDDEN STATE
# -------------
#     [position, velocity]
#
# SENSOR
# ------
#     raw = tanh(M @ state + bias) + noise
#
# DISCOVERY NEVER RECEIVES HIDDEN STATE.
#
# Hidden state is used ONLY for evaluation.
#
# V20 preserves the successful V19 tests:
#
#   1. Raw sensor baseline
#   2. Unsupervised 2D representation
#   3. Held-out affine identifiability
#   4. Held-out nonlinear identifiability
#   5. Permutation control
#
# V20 changes the dynamical audit:
#
#   6. Continuous derivative model remains diagnostic
#   7. Discrete latent transition model
#   8. One-step held-out prediction
#   9. Multi-step held-out rollout
#  10. Stability guard
#  11. Multi-trajectory generalization
#  12. Noise robustness
#
# IMPORTANT
# ---------
# No hidden state enters representation fitting.
# No hidden state enters dynamics discovery.
# Hidden state is only used AFTER prediction for scoring.
#
# ============================================================


# ============================================================
# HIDDEN REALITY
# ============================================================

class HiddenRealityV20:

    def __init__(
        self,
        seed: int,
        noise_std: float = 0.02
    ):
        self.rng = np.random.default_rng(seed)

        self.delta = 0.1
        self.alpha = -1.0
        self.beta = 1.0
        self.noise_std = noise_std

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
        steps: int = 180,
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
                    self.noise_std,
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
    n_train: int = 12,
    n_test: int = 6,
    steps: int = 180,
    noise_std: float = 0.02
):

    rng = np.random.default_rng(seed)

    reality = HiddenRealityV20(
        seed=seed,
        noise_std=noise_std
    )

    train_raw = []
    train_hidden = []

    test_raw = []
    test_hidden = []

    def sample_initial_condition():

        while True:

            pos0 = rng.uniform(-0.9, 0.9)
            vel0 = rng.uniform(-0.9, 0.9)

            if (
                abs(pos0) > 0.08
                or abs(vel0) > 0.08
            ):
                return pos0, vel0

    for _ in range(n_train):

        pos0, vel0 = sample_initial_condition()

        raw, hidden = reality.rollout(
            pos0,
            vel0,
            steps=steps
        )

        train_raw.append(raw)
        train_hidden.append(hidden)

    for _ in range(n_test):

        pos0, vel0 = sample_initial_condition()

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
# METRICS
# ============================================================

def rmse(actual, predicted):

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    return float(
        np.sqrt(
            np.mean(
                (actual - predicted) ** 2
            )
        )
    )


def correlation(actual, predicted):

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    if (
        np.std(actual) < 1e-10
        or np.std(predicted) < 1e-10
    ):
        return np.nan

    return float(
        np.corrcoef(
            actual,
            predicted
        )[0, 1]
    )


# ============================================================
# UNSUPERVISED REPRESENTATION
# ============================================================

class RepresentationV20:

    def __init__(self):

        self.mean = None
        self.std = None
        self.components = None

    def fit_transform(self, train_raw):

        flat = np.vstack(train_raw)

        self.mean = np.mean(
            flat,
            axis=0
        )

        self.std = (
            np.std(
                flat,
                axis=0
            )
            + 1e-8
        )

        standardized = (
            flat - self.mean
        ) / self.std

        covariance = (
            standardized.T
            @ standardized
            / max(
                1,
                len(standardized) - 1
            )
        )

        eigenvalues, eigenvectors = np.linalg.eigh(
            covariance
        )

        order = np.argsort(
            eigenvalues
        )[::-1]

        self.components = eigenvectors[
            :, order[:2]
        ]

        # Deterministic sign convention.
        for j in range(
            self.components.shape[1]
        ):

            idx = np.argmax(
                np.abs(
                    self.components[:, j]
                )
            )

            if self.components[idx, j] < 0:
                self.components[:, j] *= -1.0

        result = []

        start = 0

        for trajectory in train_raw:

            n = len(trajectory)

            block = standardized[
                start:start + n
            ]

            z = block @ self.components

            result.append(z)

            start += n

        return result

    def transform(self, raw):

        if (
            self.mean is None
            or self.std is None
            or self.components is None
        ):
            raise RuntimeError(
                "Representation must be fitted first."
            )

        result = []

        for trajectory in raw:

            standardized = (
                trajectory - self.mean
            ) / self.std

            z = (
                standardized
                @ self.components
            )

            result.append(z)

        return result


# ============================================================
# AFFINE MAPPING
# ============================================================

def affine_fit_predict(
    train_z,
    train_hidden,
    test_z
):

    A = np.hstack([
        train_z,
        np.ones(
            (len(train_z), 1)
        )
    ])

    B = np.hstack([
        test_z,
        np.ones(
            (len(test_z), 1)
        )
    ])

    W = np.linalg.lstsq(
        A,
        train_hidden,
        rcond=None
    )[0]

    return B @ W


# ============================================================
# POLYNOMIAL MAPPING
# ============================================================

def polynomial_features(z):

    z = np.asarray(z)

    x = z[:, 0]
    y = z[:, 1]

    return np.column_stack([
        np.ones(len(z)),
        x,
        y,

        x * x,
        x * y,
        y * y,

        x ** 3,
        (x ** 2) * y,
        x * (y ** 2),
        y ** 3
    ])


def polynomial_fit_predict(
    train_z,
    train_hidden,
    test_z
):

    A = polynomial_features(
        train_z
    )

    B = polynomial_features(
        test_z
    )

    W = np.linalg.lstsq(
        A,
        train_hidden,
        rcond=None
    )[0]

    return B @ W


# ============================================================
# RAW SENSOR BASELINE
# ============================================================

def raw_baseline(
    train_raw,
    train_hidden,
    test_raw
):

    train_x = np.vstack(
        train_raw
    )

    test_x = np.vstack(
        test_raw
    )

    return affine_fit_predict(
        train_x,
        np.vstack(train_hidden),
        test_x
    )


# ============================================================
# DISCRETE LATENT DYNAMICS
# ============================================================
#
# Instead of estimating dz/dt from noisy PCA trajectories,
# V20 learns:
#
#       z(t+1) = F(z(t))
#
# directly.
#
# This avoids numerical differentiation amplifying sensor noise.
#
# ============================================================

def transition_features(z):

    z = np.asarray(z)

    x = z[:, 0]
    y = z[:, 1]

    return np.column_stack([
        np.ones(len(z)),
        x,
        y,

        x * x,
        x * y,
        y * y,

        x ** 3,
        (x ** 2) * y,
        x * (y ** 2),
        y ** 3
    ])


def build_transition_dataset(
    trajectories
):

    X = []
    Y = []

    for trajectory in trajectories:

        z = np.asarray(
            trajectory,
            dtype=np.float64
        )

        if len(z) < 2:
            continue

        X.append(
            z[:-1]
        )

        Y.append(
            z[1:]
        )

    if not X:

        raise RuntimeError(
            "No valid transition data."
        )

    return (
        np.vstack(X),
        np.vstack(Y)
    )


def fit_ridge(
    X,
    Y,
    ridge=1e-5
):

    n_features = X.shape[1]

    regularizer = (
        ridge
        * np.eye(n_features)
    )

    # Do not penalize intercept.
    regularizer[0, 0] = 0.0

    lhs = (
        X.T @ X
        + regularizer
    )

    rhs = X.T @ Y

    return np.linalg.solve(
        lhs,
        rhs
    )


def fit_discrete_dynamics(
    trajectories,
    ridge=1e-5
):

    X_raw, Y = build_transition_dataset(
        trajectories
    )

    X = transition_features(
        X_raw
    )

    W = fit_ridge(
        X,
        Y,
        ridge=ridge
    )

    return W


def predict_next(
    z,
    W
):

    z = np.asarray(
        z,
        dtype=np.float64
    ).reshape(1, 2)

    features = transition_features(
        z
    )

    return (
        features @ W
    )[0]


def rollout_discrete(
    z0,
    W,
    steps,
    max_abs=10.0
):

    z = np.asarray(
        z0,
        dtype=np.float64
    ).copy()

    trajectory = [
        z.copy()
    ]

    for _ in range(
        steps - 1
    ):

        z_next = predict_next(
            z,
            W
        )

        if not np.all(
            np.isfinite(z_next)
        ):
            return None

        if np.any(
            np.abs(z_next)
            > max_abs
        ):
            return None

        z = z_next

        trajectory.append(
            z.copy()
        )

    return np.asarray(
        trajectory
    )


# ============================================================
# DIRECT IDENTIFIABILITY AUDIT
# ============================================================

class AuditV20:

    def __init__(
        self,
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    ):

        self.train_raw = train_raw
        self.train_hidden = train_hidden

        self.test_raw = test_raw
        self.test_hidden = test_hidden

        self.rep = RepresentationV20()

        self.train_z = None
        self.test_z = None

    def flatten(
        self,
        trajectories
    ):

        return np.vstack(
            trajectories
        )

    def prepare(self):

        self.train_z = (
            self.rep.fit_transform(
                self.train_raw
            )
        )

        self.test_z = (
            self.rep.transform(
                self.test_raw
            )
        )

    def direct_test(self):

        train_z = self.flatten(
            self.train_z
        )

        test_z = self.flatten(
            self.test_z
        )

        train_h = self.flatten(
            self.train_hidden
        )

        test_h = self.flatten(
            self.test_hidden
        )

        train_std = np.std(
            train_h,
            axis=0
        )

        test_std = np.std(
            test_h,
            axis=0
        )

        if np.any(
            train_std < 1e-4
        ):
            raise RuntimeError(
                "Training hidden state is degenerate."
            )

        if np.any(
            test_std < 1e-4
        ):
            raise RuntimeError(
                "Test hidden state is degenerate."
            )

        affine_pred = affine_fit_predict(
            train_z,
            train_h,
            test_z
        )

        poly_pred = polynomial_fit_predict(
            train_z,
            train_h,
            test_z
        )

        raw_pred = raw_baseline(
            self.train_raw,
            self.train_hidden,
            self.test_raw
        )

        constant = np.mean(
            train_h,
            axis=0
        )

        constant_pred = np.tile(
            constant,
            (len(test_h), 1)
        )

        affine_rmse = rmse(
            test_h,
            affine_pred
        )

        poly_rmse = rmse(
            test_h,
            poly_pred
        )

        raw_rmse = rmse(
            test_h,
            raw_pred
        )

        constant_rmse = rmse(
            test_h,
            constant_pred
        )

        affine_pos = correlation(
            test_h[:, 0],
            affine_pred[:, 0]
        )

        affine_vel = correlation(
            test_h[:, 1],
            affine_pred[:, 1]
        )

        poly_pos = correlation(
            test_h[:, 0],
            poly_pred[:, 0]
        )

        poly_vel = correlation(
            test_h[:, 1],
            poly_pred[:, 1]
        )

        raw_pos = correlation(
            test_h[:, 0],
            raw_pred[:, 0]
        )

        raw_vel = correlation(
            test_h[:, 1],
            raw_pred[:, 1]
        )

        affine_improvement = (
            1.0
            - affine_rmse
            / constant_rmse
        )

        poly_improvement = (
            1.0
            - poly_rmse
            / constant_rmse
        )

        raw_improvement = (
            1.0
            - raw_rmse
            / constant_rmse
        )

        affine_pass = (
            affine_rmse < 0.10
            and affine_pos > 0.95
            and affine_vel > 0.95
            and affine_improvement > 0.90
        )

        nonlinear_pass = (
            poly_rmse < 0.10
            and poly_pos > 0.95
            and poly_vel > 0.95
            and poly_improvement > 0.90
        )

        print("\n" + "=" * 72)
        print(
            "[DIRECT IDENTIFIABILITY AUDIT]"
        )
        print("=" * 72)

        print(
            f"[DATA] Train trajectories: "
            f"{len(self.train_raw)}"
        )

        print(
            f"[DATA] Test trajectories: "
            f"{len(self.test_raw)}"
        )

        print(
            f"[HIDDEN] Train std: "
            f"pos={train_std[0]:.6f}, "
            f"vel={train_std[1]:.6f}"
        )

        print(
            f"[HIDDEN] Test std: "
            f"pos={test_std[0]:.6f}, "
            f"vel={test_std[1]:.6f}"
        )

        print(
            "\n[UNSUPERVISED REPRESENTATION]"
        )

        print(
            "Representation: "
            "standardized raw sensors -> PCA(2)"
        )

        print(
            f"Latent dimensionality: "
            f"{train_z.shape[1]}"
        )

        print("\n[RAW SENSOR BASELINE]")

        print(
            f"RMSE: {raw_rmse:.9f}"
        )

        print(
            f"Position correlation: "
            f"{raw_pos:.9f}"
        )

        print(
            f"Velocity correlation: "
            f"{raw_vel:.9f}"
        )

        print(
            "\n[DISCOVERED 2D REPRESENTATION — AFFINE]"
        )

        print(
            f"RMSE: {affine_rmse:.9f}"
        )

        print(
            f"Position correlation: "
            f"{affine_pos:.9f}"
        )

        print(
            f"Velocity correlation: "
            f"{affine_vel:.9f}"
        )

        print(
            "\n[DISCOVERED 2D REPRESENTATION — NONLINEAR]"
        )

        print(
            f"RMSE: {poly_rmse:.9f}"
        )

        print(
            f"Position correlation: "
            f"{poly_pos:.9f}"
        )

        print(
            f"Velocity correlation: "
            f"{poly_vel:.9f}"
        )

        print("\n[BASELINE]")

        print(
            f"Constant RMSE: "
            f"{constant_rmse:.9f}"
        )

        print(
            f"Raw improvement: "
            f"{100 * raw_improvement:.3f}%"
        )

        print(
            f"Affine improvement: "
            f"{100 * affine_improvement:.3f}%"
        )

        print(
            f"Polynomial improvement: "
            f"{100 * poly_improvement:.3f}%"
        )

        return {
            "affine_rmse": affine_rmse,
            "affine_pos": affine_pos,
            "affine_vel": affine_vel,

            "poly_rmse": poly_rmse,
            "poly_pos": poly_pos,
            "poly_vel": poly_vel,

            "raw_rmse": raw_rmse,
            "raw_pos": raw_pos,
            "raw_vel": raw_vel,

            "constant_rmse": constant_rmse,

            "affine_pass": affine_pass,
            "nonlinear_pass": nonlinear_pass
        }

    def permutation_control(self):

        train_z = self.flatten(
            self.train_z
        )

        test_z = self.flatten(
            self.test_z
        )

        train_h = self.flatten(
            self.train_hidden
        )

        test_h = self.flatten(
            self.test_hidden
        )

        rng = np.random.default_rng(
            991
        )

        shuffled = train_h.copy()

        rng.shuffle(
            shuffled,
            axis=0
        )

        pred = affine_fit_predict(
            train_z,
            shuffled,
            test_z
        )

        error = rmse(
            test_h,
            pred
        )

        print("\n" + "=" * 72)
        print(
            "[PERMUTATION CONTROL]"
        )
        print("=" * 72)

        print(
            f"Shuffled-label RMSE: "
            f"{error:.9f}"
        )

        return error


# ============================================================
# DISCRETE DYNAMICAL AUDIT
# ============================================================

def dynamical_test(
    audit: AuditV20
):

    print("\n" + "=" * 72)
    print(
        "[DISCRETE DYNAMICAL IDENTIFIABILITY AUDIT]"
    )
    print("=" * 72)

    for trajectory in audit.train_z:

        if trajectory.shape[1] != 2:

            raise RuntimeError(
                "Dynamics requires a 2D latent representation."
            )

    for trajectory in audit.test_z:

        if trajectory.shape[1] != 2:

            raise RuntimeError(
                "Dynamics requires a 2D latent representation."
            )

    # --------------------------------------------------------
    # Fit directly to z(t+1) from z(t).
    # --------------------------------------------------------

    W = fit_discrete_dynamics(
        audit.train_z,
        ridge=1e-5
    )

    # --------------------------------------------------------
    # TRAINING ONE-STEP ERROR
    # --------------------------------------------------------

    train_x, train_y = build_transition_dataset(
        audit.train_z
    )

    train_pred = (
        transition_features(train_x)
        @ W
    )

    train_one_step = rmse(
        train_y,
        train_pred
    )

    # --------------------------------------------------------
    # HELD-OUT ONE-STEP ERROR
    # --------------------------------------------------------

    test_x, test_y = build_transition_dataset(
        audit.test_z
    )

    test_pred = (
        transition_features(test_x)
        @ W
    )

    test_one_step = rmse(
        test_y,
        test_pred
    )

    print(
        f"[DYNAMICAL] Training one-step RMSE: "
        f"{train_one_step:.9f}"
    )

    print(
        f"[DYNAMICAL] Held-out one-step RMSE: "
        f"{test_one_step:.9f}"
    )

    # --------------------------------------------------------
    # MULTI-STEP ROLLOUT
    # --------------------------------------------------------

    rollout_errors = []
    rollout_valid = 0

    for actual in audit.test_z:

        if len(actual) < 5:
            continue

        predicted = rollout_discrete(
            actual[0],
            W,
            len(actual)
        )

        if predicted is None:

            rollout_errors.append(
                np.inf
            )

            continue

        rollout_valid += 1

        rollout_errors.append(
            rmse(
                actual,
                predicted
            )
        )

    if not rollout_errors:

        raise RuntimeError(
            "No valid held-out trajectories."
        )

    rollout_errors = np.asarray(
        rollout_errors,
        dtype=np.float64
    )

    finite_rollouts = rollout_errors[
        np.isfinite(rollout_errors)
    ]

    if len(finite_rollouts) == 0:

        mean_rollout = float("inf")
        worst_rollout = float("inf")

    else:

        mean_rollout = float(
            np.mean(
                finite_rollouts
            )
        )

        worst_rollout = float(
            np.max(
                finite_rollouts
            )
        )

    print(
        f"[DYNAMICAL] Valid held-out rollouts: "
        f"{rollout_valid}/{len(rollout_errors)}"
    )

    print(
        f"[DYNAMICAL] Mean latent rollout RMSE: "
        f"{mean_rollout:.9f}"
    )

    print(
        f"[DYNAMICAL] Worst latent rollout RMSE: "
        f"{worst_rollout:.9f}"
    )

    stable = (
        np.isfinite(mean_rollout)
        and np.isfinite(worst_rollout)
        and mean_rollout < 0.50
        and worst_rollout < 1.00
    )

    one_step_pass = (
        np.isfinite(test_one_step)
        and test_one_step < 0.10
    )

    dynamics_pass = (
        stable
        and one_step_pass
    )

    print(
        f"[DYNAMICAL] One-step pass: "
        f"{one_step_pass}"
    )

    print(
        f"[DYNAMICAL] Rollout stability pass: "
        f"{stable}"
    )

    print(
        f"[DYNAMICAL] Overall dynamics pass: "
        f"{dynamics_pass}"
    )

    return {
        "train_one_step": train_one_step,
        "test_one_step": test_one_step,
        "mean_rollout": mean_rollout,
        "worst_rollout": worst_rollout,
        "valid_rollouts": rollout_valid,
        "total_rollouts": len(rollout_errors),
        "dynamics_pass": dynamics_pass,
        "W": W
    }


# ============================================================
# CONTINUOUS SINDY DIAGNOSTIC
# ============================================================
#
# SINDy is retained here only as a diagnostic.
#
# V19 demonstrated that noisy finite differences + polynomial
# regression can produce unstable vector fields.
#
# Therefore SINDy is NOT allowed to determine the primary
# identifiability verdict in V20.
#
# ============================================================

def sindy_features(z):

    z = np.asarray(z)

    x = z[:, 0]
    y = z[:, 1]

    return np.column_stack([
        np.ones(len(z)),
        x,
        y,

        x * x,
        x * y,
        y * y,

        x ** 3,
        (x ** 2) * y,
        x * (y ** 2),
        y ** 3
    ])


def sindy_diagnostic(
    trajectories,
    dt=0.05
):

    derivative_errors = []

    for trajectory in trajectories:

        z = np.asarray(
            trajectory,
            dtype=np.float64
        )

        if len(z) < 5:
            continue

        dz = np.gradient(
            z,
            dt,
            axis=0
        )

        A = sindy_features(
            z
        )

        predicted = np.zeros_like(
            dz
        )

        for k in range(2):

            c = np.linalg.lstsq(
                A,
                dz[:, k],
                rcond=None
            )[0]

            predicted[:, k] = (
                A @ c
            )

        derivative_errors.append(
            rmse(
                dz,
                predicted
            )
        )

    if not derivative_errors:

        return float("inf")

    return float(
        np.mean(
            derivative_errors
        )
    )


# ============================================================
# NOISE ROBUSTNESS
# ============================================================

def noise_test(seed):

    print("\n" + "=" * 72)
    print(
        "[NOISE ROBUSTNESS AUDIT]"
    )
    print("=" * 72)

    levels = [
        0.02,
        0.05,
        0.10
    ]

    results = []

    for noise in levels:

        (
            train_raw,
            train_hidden,
            test_raw,
            test_hidden
        ) = make_dataset(
            seed=seed,
            noise_std=noise
        )

        audit = AuditV20(
            train_raw,
            train_hidden,
            test_raw,
            test_hidden
        )

        audit.prepare()

        direct = audit.direct_test()

        results.append({
            "noise": noise,
            "direct": direct
        })

        print(
            f"\n[NOISE {noise:.2f}] "
            f"Affine RMSE="
            f"{direct['affine_rmse']:.6f} "
            f"Nonlinear RMSE="
            f"{direct['poly_rmse']:.6f}"
        )

    return results


# ============================================================
# TRIAL
# ============================================================

def run_trial(seed):

    print("\n")
    print("#" * 72)
    print(
        f"AEGIS V20 TRIAL {seed}"
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

    audit = AuditV20(
        train_raw,
        train_hidden,
        test_raw,
        test_hidden
    )

    audit.prepare()

    direct = audit.direct_test()

    permutation_error = (
        audit.permutation_control()
    )

    dynamic = dynamical_test(
        audit
    )

    sindy_error = sindy_diagnostic(
        audit.train_z
    )

    print(
        f"[SINDy DIAGNOSTIC] "
        f"Derivative RMSE: "
        f"{sindy_error:.9f}"
    )

    return {
        "direct": direct,
        "permutation_error":
            permutation_error,
        "dynamic": dynamic,
        "sindy_derivative_rmse":
            sindy_error
    }


# ============================================================
# FINAL AUDIT
# ============================================================

def main():

    random.seed(42)
    np.random.seed(42)

    print("=" * 72)
    print(
        "AEGIS V20 — IDENTIFIABILITY + STABLE DYNAMICAL AUDIT"
    )
    print("=" * 72)

    seeds = [
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51
    ]

    results = []

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
                f"{type(exc).__name__}: {exc}"
            )

    print("\n" + "=" * 72)
    print(
        "AEGIS V20 FINAL AUDIT"
    )
    print("=" * 72)

    if len(results) != len(seeds):

        print(
            "[FINAL] FAIL — "
            "not all trials completed."
        )

        print(
            "[FINAL] This is an execution failure, "
            "not an identifiability verdict."
        )

        return

    # --------------------------------------------------------
    # DIRECT RESULTS
    # --------------------------------------------------------

    affine_passes = sum(
        r["direct"]["affine_pass"]
        for r in results
    )

    nonlinear_passes = sum(
        r["direct"]["nonlinear_pass"]
        for r in results
    )

    mean_affine = float(
        np.mean([
            r["direct"]["affine_rmse"]
            for r in results
        ])
    )

    mean_poly = float(
        np.mean([
            r["direct"]["poly_rmse"]
            for r in results
        ])
    )

    # --------------------------------------------------------
    # DYNAMICS
    # --------------------------------------------------------

    dynamics_passes = sum(
        r["dynamic"]["dynamics_pass"]
        for r in results
    )

    one_step_mean = float(
        np.mean([
            r["dynamic"]["test_one_step"]
            for r in results
        ])
    )

    rollout_means = np.array([
        r["dynamic"]["mean_rollout"]
        for r in results
    ])

    finite_rollout_means = (
        rollout_means[
            np.isfinite(rollout_means)
        ]
    )

    if len(finite_rollout_means):

        mean_dynamic = float(
            np.mean(
                finite_rollout_means
            )
        )

        worst_dynamic = float(
            np.max(
                finite_rollout_means
            )
        )

    else:

        mean_dynamic = float("inf")
        worst_dynamic = float("inf")

    # --------------------------------------------------------
    # PERMUTATION
    # --------------------------------------------------------

    permutation_errors = np.array([
        r["permutation_error"]
        for r in results
    ])

    mean_permutation = float(
        np.mean(
            permutation_errors
        )
    )

    # --------------------------------------------------------
    # SINDY DIAGNOSTIC
    # --------------------------------------------------------

    mean_sindy = float(
        np.mean([
            r["sindy_derivative_rmse"]
            for r in results
        ])
    )

    # --------------------------------------------------------
    # PRINT SUMMARY
    # --------------------------------------------------------

    print(
        f"[FINAL] Valid trials: "
        f"{len(results)}/{len(seeds)}"
    )

    print(
        f"[FINAL] Affine passes: "
        f"{affine_passes}/{len(results)}"
    )

    print(
        f"[FINAL] Nonlinear passes: "
        f"{nonlinear_passes}/{len(results)}"
    )

    print(
        f"[FINAL] Dynamics passes: "
        f"{dynamics_passes}/{len(results)}"
    )

    print(
        f"[FINAL] Mean affine RMSE: "
        f"{mean_affine:.9f}"
    )

    print(
        f"[FINAL] Mean nonlinear RMSE: "
        f"{mean_poly:.9f}"
    )

    print(
        f"[FINAL] Mean held-out one-step RMSE: "
        f"{one_step_mean:.9f}"
    )

    print(
        f"[FINAL] Mean latent rollout RMSE: "
        f"{mean_dynamic:.9f}"
    )

    print(
        f"[FINAL] Worst latent rollout RMSE: "
        f"{worst_dynamic:.9f}"
    )

    print(
        f"[FINAL] Mean permutation-control RMSE: "
        f"{mean_permutation:.9f}"
    )

    print(
        f"[FINAL] Mean SINDy derivative RMSE: "
        f"{mean_sindy:.9f}"
    )

    # --------------------------------------------------------
    # PROMOTION GATES
    # --------------------------------------------------------

    all_affine = (
        affine_passes
        == len(results)
    )

    all_nonlinear = (
        nonlinear_passes
        == len(results)
    )

    all_dynamics = (
        dynamics_passes
        == len(results)
    )

    permutation_pass = (
        mean_permutation
        > mean_affine * 1.5
    )

    # --------------------------------------------------------
    # FINAL CLASSIFICATION
    # --------------------------------------------------------

    if (
        all_affine
        and all_dynamics
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "FULL AFFINE DYNAMICAL IDENTIFIABILITY "
            "ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The unsupervised 2D representation "
            "generalizes to unseen trajectories."
        )

        print(
            "[FINAL RESULT] "
            "The discovered latent transition law "
            "generalizes through forward rollout."
        )

        print(
            "[FINAL RESULT] "
            "Permutation control rejects arbitrary "
            "label correspondence."
        )

    elif (
        all_nonlinear
        and all_dynamics
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "FULL NONLINEAR DYNAMICAL "
            "IDENTIFIABILITY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The unsupervised representation preserves "
            "the hidden physical state."
        )

        print(
            "[FINAL RESULT] "
            "The relationship is nonlinear rather "
            "than requiring affine equivalence."
        )

        print(
            "[FINAL RESULT] "
            "Forward latent dynamics generalize."
        )

    elif (
        all_affine
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "STATE IDENTIFIABILITY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The unsupervised representation consistently "
            "recovers the hidden state correspondence."
        )

        print(
            "[FINAL RESULT] "
            "DYNAMICAL IDENTIFIABILITY IS NOT ESTABLISHED."
        )

        print(
            "[FINAL RESULT] "
            "The remaining scientific problem is "
            "latent dynamical discovery."
        )

    elif (
        all_nonlinear
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "NONLINEAR STATE IDENTIFIABILITY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The representation preserves the hidden "
            "state through a nonlinear coordinate map."
        )

        print(
            "[FINAL RESULT] "
            "Dynamical identifiability remains unresolved."
        )

    else:

        print(
            "\n[FINAL RESULT] "
            "IDENTIFIABILITY NOT FULLY ESTABLISHED"
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
