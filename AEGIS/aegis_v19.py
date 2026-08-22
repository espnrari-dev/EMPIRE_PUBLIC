#!/data/data/com.termux/files/usr/bin/python

import numpy as np
import random
from typing import Tuple


# ============================================================
# AEGIS V19 — FULL IDENTIFIABILITY AUDIT
# ============================================================
#
# PURPOSE
# -------
# Determine whether a hidden physical dynamical system can be
# reconstructed from sensor observations alone.
#
# Hidden state:
#
#     [position, velocity]
#
# Sensor:
#
#     raw = tanh(M @ state + bias) + noise
#
# IMPORTANT:
# Discovery NEVER receives hidden state.
#
# Hidden state is used only for evaluation.
#
# V19 AUDITS:
#
#   1. RAW OBSERVABILITY
#   2. UNSUPERVISED 2D REPRESENTATION
#   3. HELD-OUT AFFINE IDENTIFIABILITY
#   4. HELD-OUT NONLINEAR IDENTIFIABILITY
#   5. DYNAMICAL IDENTIFIABILITY
#   6. FORWARD ROLLOUT
#   7. MULTI-TRAJECTORY GENERALIZATION
#   8. PERMUTATION CONTROL
#   9. RAW-SENSOR BASELINE
#  10. NOISE ROBUSTNESS
#
# NO RESULT IS PROMOTED FROM ONE METRIC.
#
# ============================================================


# ============================================================
# HIDDEN REALITY
# ============================================================

class HiddenRealityV19:

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

    reality = HiddenRealityV19(
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


def normalized_rmse(actual, predicted):

    actual = np.asarray(actual)

    scale = np.std(
        actual,
        axis=0
    )

    scale = np.maximum(
        scale,
        1e-12
    )

    return float(
        np.sqrt(
            np.mean(
                (
                    (actual - predicted)
                    / scale
                ) ** 2
            )
        )
    )


# ============================================================
# UNSUPERVISED REPRESENTATION
# ============================================================

class RepresentationV19:

    """
    Unsupervised sensor representation.

    Discovery sees ONLY raw sensors.

    The representation is:

        raw -> standardized sensor space -> PCA -> 2D latent

    Hidden state is never used by this class.
    """

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

        components = eigenvectors[
            :, order[:2]
        ]

        # Deterministic sign convention.
        for j in range(
            components.shape[1]
        ):

            idx = np.argmax(
                np.abs(
                    components[:, j]
                )
            )

            if components[idx, j] < 0:
                components[:, j] *= -1.0

        self.components = components

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
# SINDY — CUBIC LIBRARY
# ============================================================

def sindy_features(z):

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


def discover_sindy(
    trajectories,
    dt=0.05,
    threshold=0.05
):

    coefficients = []

    for trajectory in trajectories:

        z = np.asarray(
            trajectory,
            dtype=np.float64
        )

        if len(z) < 5:
            continue

        if z.shape[1] != 2:
            raise ValueError(
                "SINDy requires a 2D latent representation; "
                f"received shape {z.shape}."
            )

        dz = np.gradient(
            z,
            dt,
            axis=0
        )

        A = sindy_features(z)

        local_coeffs = []

        for k in range(2):

            c = np.linalg.lstsq(
                A,
                dz[:, k],
                rcond=None
            )[0]

            for _ in range(10):

                small = (
                    np.abs(c)
                    < threshold
                )

                if np.all(small):

                    c[:] = 0.0

                    break

                active = ~small

                new_c = np.zeros_like(c)

                new_c[active] = np.linalg.lstsq(
                    A[:, active],
                    dz[:, k],
                    rcond=None
                )[0]

                c = new_c

            local_coeffs.append(c)

        coefficients.append(
            local_coeffs
        )

    if not coefficients:

        raise RuntimeError(
            "SINDy received no valid trajectories."
        )

    return coefficients


def aggregate_sindy(
    coefficients
):

    result = []

    for k in range(2):

        values = np.vstack([
            c[k]
            for c in coefficients
        ])

        result.append(
            np.median(
                values,
                axis=0
            )
        )

    return result


# ============================================================
# LATENT DYNAMICS
# ============================================================

def derivative(
    z,
    coeffs
):

    x = float(z[0])
    y = float(z[1])

    features = np.array([
        1.0,

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

    return np.array([
        np.dot(
            coeffs[0],
            features
        ),
        np.dot(
            coeffs[1],
            features
        )
    ])


def integrate(
    z0,
    coeffs,
    steps,
    dt=0.05
):

    z = np.asarray(
        z0,
        dtype=np.float64
    ).copy()

    if z.shape != (2,):
        raise ValueError(
            "Integrator requires a 2D latent state; "
            f"received shape {z.shape}."
        )

    trajectory = [
        z.copy()
    ]

    for _ in range(
        steps - 1
    ):

        k1 = derivative(
            z,
            coeffs
        )

        k2 = derivative(
            z + 0.5 * dt * k1,
            coeffs
        )

        k3 = derivative(
            z + 0.5 * dt * k2,
            coeffs
        )

        k4 = derivative(
            z + dt * k3,
            coeffs
        )

        z = (
            z
            + (dt / 6.0)
            * (
                k1
                + 2.0 * k2
                + 2.0 * k3
                + k4
            )
        )

        trajectory.append(
            z.copy()
        )

    return np.asarray(
        trajectory
    )


# ============================================================
# AUDIT
# ============================================================

class AuditV19:

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

        self.rep = RepresentationV19()

        self.train_z = None
        self.test_z = None

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

    def flatten(
        self,
        trajectories
    ):

        return np.vstack(
            trajectories
        )

    # --------------------------------------------------------
    # DIRECT IDENTIFIABILITY
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # UNSUPERVISED REPRESENTATION -> HIDDEN STATE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RAW SENSOR BASELINE
        # ----------------------------------------------------

        raw_pred = raw_baseline(
            self.train_raw,
            self.train_hidden,
            self.test_raw
        )

        # ----------------------------------------------------
        # CONSTANT BASELINE
        # ----------------------------------------------------

        constant = np.mean(
            train_h,
            axis=0
        )

        constant_pred = np.tile(
            constant,
            (len(test_h), 1)
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

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
            "\n[DISCOVERED 2D REPRESENTATION — "
            "NONLINEAR]"
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

        # ----------------------------------------------------
        # PROMOTION GATES
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # PERMUTATION CONTROL
    # --------------------------------------------------------

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

        rng = np.random.default_rng(991)

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
# DYNAMICAL AUDIT
# ============================================================

def dynamical_test(
    audit: AuditV19,
    dt=0.05
):

    print("\n" + "=" * 72)
    print(
        "[DYNAMICAL IDENTIFIABILITY AUDIT]"
    )
    print("=" * 72)

    # --------------------------------------------------------
    # HARD DIMENSIONALITY GUARD
    # --------------------------------------------------------

    for trajectory in audit.train_z:

        if trajectory.shape[1] != 2:

            raise RuntimeError(
                "Dynamical audit requires a 2D "
                "unsupervised representation."
            )

    for trajectory in audit.test_z:

        if trajectory.shape[1] != 2:

            raise RuntimeError(
                "Dynamical audit requires a 2D "
                "unsupervised representation."
            )

    coefficients = discover_sindy(
        audit.train_z,
        dt=dt,
        threshold=0.05
    )

    coeffs = aggregate_sindy(
        coefficients
    )

    print(
        "[SINDy] Aggregated discovered equations:"
    )

    names = [
        "1",
        "x",
        "y",
        "x^2",
        "xy",
        "y^2",
        "x^3",
        "x^2y",
        "xy^2",
        "y^3"
    ]

    for k, c in enumerate(coeffs):

        active = np.where(
            np.abs(c) > 1e-6
        )[0]

        if len(active) == 0:

            print(
                f"  dz{k+1}/dt = 0"
            )

        else:

            eq = " + ".join(
                f"{c[i]:.4f}*{names[i]}"
                for i in active
            )

            print(
                f"  dz{k+1}/dt = {eq}"
            )

    # --------------------------------------------------------
    # TRAINING ONE-STEP DERIVATIVE ERROR
    # --------------------------------------------------------

    derivative_errors = []

    for trajectory in audit.train_z:

        z = np.asarray(
            trajectory
        )

        actual_dz = np.gradient(
            z,
            dt,
            axis=0
        )

        predicted_dz = np.vstack([
            derivative(
                row,
                coeffs
            )
            for row in z
        ])

        derivative_errors.append(
            rmse(
                actual_dz,
                predicted_dz
            )
        )

    derivative_rmse = float(
        np.mean(
            derivative_errors
        )
    )

    print(
        f"[DYNAMICAL] Training derivative RMSE: "
        f"{derivative_rmse:.9f}"
    )

    # --------------------------------------------------------
    # ONE ROLLOUT PER UNSEEN TRAJECTORY
    # --------------------------------------------------------

    rollout_errors = []

    for i in range(
        len(audit.test_z)
    ):

        actual = audit.test_z[i]

        if len(actual) < 5:
            continue

        z0 = actual[0]

        predicted = integrate(
            z0,
            coeffs,
            len(actual),
            dt
        )

        n = min(
            len(actual),
            len(predicted)
        )

        err = rmse(
            actual[:n],
            predicted[:n]
        )

        rollout_errors.append(
            err
        )

    if not rollout_errors:

        raise RuntimeError(
            "No valid held-out trajectories "
            "were available for rollout."
        )

    rollout_errors = np.asarray(
        rollout_errors
    )

    mean_rollout = float(
        np.mean(
            rollout_errors
        )
    )

    worst_rollout = float(
        np.max(
            rollout_errors
        )
    )

    print(
        f"[DYNAMICAL] Mean latent rollout RMSE: "
        f"{mean_rollout:.9f}"
    )

    print(
        f"[DYNAMICAL] Worst latent rollout RMSE: "
        f"{worst_rollout:.9f}"
    )

    return {
        "mean_rollout": mean_rollout,
        "worst_rollout": worst_rollout,
        "derivative_rmse": derivative_rmse,
        "coeffs": coeffs
    }


# ============================================================
# NOISE ROBUSTNESS
# ============================================================

def noise_test(seed):

    print("\n" + "=" * 72)
    print(
        "[NOISE ROBUSTNESS]"
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

        audit = AuditV19(
            train_raw,
            train_hidden,
            test_raw,
            test_hidden
        )

        audit.prepare()

        result = audit.direct_test()

        results.append(
            (
                noise,
                result
            )
        )

    return results


# ============================================================
# TRIAL
# ============================================================

def run_trial(
    seed
):

    print("\n")
    print("#" * 72)
    print(
        f"AEGIS V19 TRIAL {seed}"
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

    audit = AuditV19(
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

    return {
        "direct": direct,
        "permutation_error":
            permutation_error,
        "dynamic": dynamic
    }


# ============================================================
# FINAL AUDIT
# ============================================================

def main():

    random.seed(42)
    np.random.seed(42)

    print("=" * 72)
    print(
        "AEGIS V19 — FULL IDENTIFIABILITY AUDIT"
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
        "AEGIS V19 FINAL AUDIT"
    )
    print("=" * 72)

    if len(results) != len(seeds):

        print(
            "[FINAL] FAIL — "
            "not all trials completed."
        )

        return

    affine_passes = sum(
        r["direct"]["affine_pass"]
        for r in results
    )

    nonlinear_passes = sum(
        r["direct"]["nonlinear_pass"]
        for r in results
    )

    mean_affine = np.mean([
        r["direct"]["affine_rmse"]
        for r in results
    ])

    mean_poly = np.mean([
        r["direct"]["poly_rmse"]
        for r in results
    ])

    mean_dynamic = np.mean([
        r["dynamic"]["mean_rollout"]
        for r in results
    ])

    worst_dynamic = np.max([
        r["dynamic"]["worst_rollout"]
        for r in results
    ])

    mean_derivative = np.mean([
        r["dynamic"]["derivative_rmse"]
        for r in results
    ])

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
        f"[FINAL] Mean affine RMSE: "
        f"{mean_affine:.9f}"
    )

    print(
        f"[FINAL] Mean polynomial RMSE: "
        f"{mean_poly:.9f}"
    )

    print(
        f"[FINAL] Mean derivative RMSE: "
        f"{mean_derivative:.9f}"
    )

    print(
        f"[FINAL] Mean dynamical rollout RMSE: "
        f"{mean_dynamic:.9f}"
    )

    print(
        f"[FINAL] Worst dynamical rollout RMSE: "
        f"{worst_dynamic:.9f}"
    )

    # --------------------------------------------------------
    # PERMUTATION SANITY
    # --------------------------------------------------------

    permutation_errors = np.array([
        r["permutation_error"]
        for r in results
    ])

    print(
        f"[FINAL] Mean permutation-control RMSE: "
        f"{np.mean(permutation_errors):.9f}"
    )

    # --------------------------------------------------------
    # FINAL PROMOTION
    # --------------------------------------------------------

    all_affine = (
        affine_passes == len(results)
    )

    all_nonlinear = (
        nonlinear_passes == len(results)
    )

    dynamics_pass = (
        mean_dynamic < 0.25
        and worst_dynamic < 0.50
    )

    permutation_pass = (
        np.mean(permutation_errors)
        >
        mean_affine * 1.5
    )

    if (
        all_affine
        and dynamics_pass
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "FULL AFFINE IDENTIFIABILITY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "All independent held-out trials passed."
        )

        print(
            "[FINAL RESULT] "
            "The unsupervised 2D sensor representation "
            "is consistently affinely related to "
            "the hidden physical state."
        )

        print(
            "[FINAL RESULT] "
            "The discovered dynamics generalize "
            "forward on unseen trajectories."
        )

        print(
            "[FINAL RESULT] "
            "Permutation control confirms that "
            "the correspondence is not produced "
            "by arbitrary shuffled labels."
        )

    elif (
        all_nonlinear
        and dynamics_pass
        and permutation_pass
    ):

        print(
            "\n[FINAL RESULT] "
            "FULL NONLINEAR IDENTIFIABILITY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The unsupervised 2D representation "
            "consistently preserves the hidden "
            "physical state through a nonlinear "
            "coordinate relationship."
        )

        print(
            "[FINAL RESULT] "
            "Affine equivalence is NOT claimed."
        )

    else:

        print(
            "\n[FINAL RESULT] "
            "IDENTIFIABILITY NOT FULLY ESTABLISHED"
        )

        print(
            "[FINAL RESULT] "
            "The audit isolated the remaining "
            "scientific gap instead of promoting "
            "an incomplete result."
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
