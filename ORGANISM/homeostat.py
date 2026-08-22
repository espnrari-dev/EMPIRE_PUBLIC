import numpy as np

class Homeostat:
    def __init__(self, seed=42):
        self.V_MAX = 1.0
        self.x = np.array([0.5, -0.3, 0.8, -0.4])
        self.d = np.array([-0.2, 0.6, -0.1, 0.3])
        self.M = np.eye(4) + np.array([[0.1, 0.0, 0.0, 0.0],
                                       [0.0, -0.1, 0.0, 0.0],
                                       [0.0, 0.0, 0.1, 0.0],
                                       [0.0, 0.0, 0.0, -0.1]])
        self.dt = 0.05
        self.eta = 0.05
        self.rng = np.random.default_rng(seed)

    def step(self):
        dx = (self.M @ self.x + self.d) * self.dt
        self.x = self.x + dx
        if np.any(np.abs(self.x) >= self.V_MAX):
            idx = np.argmax(np.abs(self.x))
            sign = np.sign(self.x[idx])
            self.M[idx, :] -= self.eta * sign * self.x
        return self.x.copy()

    def run(self, steps=2000):
        print("Starting deterministic homeostat master loop...")
        for t in range(steps):
            x = self.step()
            if t % 200 == 0:
                max_abs = np.max(np.abs(x))
                viable = "VIABLE" if max_abs < self.V_MAX else "THREAT"
                print(f"Step {t:4d} | max|x| = {max_abs:.4f} | {viable}")
        print(f"Final state: {self.x}")
        print(f"Final viability: {'All within bounds' if np.all(np.abs(self.x) < self.V_MAX) else 'SOME VARIABLE OUT OF BOUNDS'}")

if __name__ == "__main__":
    organism = Homeostat()
    organism.run()
