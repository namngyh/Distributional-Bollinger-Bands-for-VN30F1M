"""Training-only fits for standardized one-step return innovations.

Each returned law is affine-normalized to population mean zero and variance one.
Callers must provide historical residuals only; this module never reads market data.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import logsumexp
from scipy.stats import genhyperbolic, gennorm, norm, norminvgauss, t


MODEL_NAMES = ("normal", "student_t", "ged", "nig", "gh", "normal_mixture_2")


class FitError(ValueError):
    """A candidate could not be fitted or normalized; no fallback was applied."""


@dataclass(frozen=True)
class FitConfig:
    experiment_id: str = "DISTRIBUTION-FIT-V1"
    models: tuple[str, ...] = MODEL_NAMES
    min_observations: int = 80
    mle_max_iter: int = 150
    mle_starts: int = 3
    mixture_max_iter: int = 300
    mixture_starts: int = 5
    mixture_tolerance: float = 1e-5
    mixture_variance_floor: float = 1e-4
    mixture_weight_floor: float = 0.01
    seed: int = 20260923

    @classmethod
    def from_json(cls, path: Path) -> "FitConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = cls(
            experiment_id=str(raw["experiment_id"]),
            models=tuple(raw["models"]),
            min_observations=int(raw["min_observations"]),
            mle_max_iter=int(raw["mle_max_iter"]),
            mle_starts=int(raw["mle_starts"]),
            mixture_max_iter=int(raw["mixture_max_iter"]),
            mixture_starts=int(raw["mixture_starts"]),
            mixture_tolerance=float(raw["mixture_tolerance"]),
            mixture_variance_floor=float(raw["mixture_variance_floor"]),
            mixture_weight_floor=float(raw["mixture_weight_floor"]),
            seed=int(raw["seed"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.experiment_id or not self.models or len(set(self.models)) != len(self.models):
            raise ValueError("Experiment ID and unique candidate models are required")
        if any(name not in MODEL_NAMES for name in self.models):
            raise ValueError("Unknown candidate distribution")
        if self.min_observations < 20 or self.mle_max_iter <= 0 or not 2 <= self.mle_starts <= 3:
            raise ValueError("Invalid MLE sample/iteration/start configuration")
        if self.mixture_max_iter <= 0 or self.mixture_starts < 2 or self.seed < 0:
            raise ValueError("Invalid mixture iterations, starts or seed")
        if not (0 < self.mixture_tolerance < 1 and 0 < self.mixture_variance_floor < 1
                and 0 < self.mixture_weight_floor < 0.5):
            raise ValueError("Invalid mixture tolerance or floors")


@dataclass(frozen=True)
class FittedDistribution:
    model: str
    parameters: dict[str, float]
    center: float
    spread: float
    n_observations: int
    log_likelihood: float
    diagnostics: dict[str, int | float | str]

    def _frozen(self):
        p = self.parameters
        if self.model == "normal":
            return norm(loc=p["loc"], scale=p["scale"])
        if self.model == "student_t":
            return t(p["df"], loc=p["loc"], scale=p["scale"])
        if self.model == "ged":
            return gennorm(p["beta"], loc=p["loc"], scale=p["scale"])
        if self.model == "nig":
            return norminvgauss(p["a"], p["b"], loc=p["loc"], scale=p["scale"])
        if self.model == "gh":
            return genhyperbolic(p["p"], p["a"], p["b"], loc=p["loc"], scale=p["scale"])
        raise ValueError("Mixture has no SciPy frozen distribution")

    def _mixture_cdf(self, raw: np.ndarray) -> np.ndarray:
        p = self.parameters
        return (p["weight_1"] * norm.cdf(raw, p["mean_1"], p["sigma_1"])
                + p["weight_2"] * norm.cdf(raw, p["mean_2"], p["sigma_2"]))

    def cdf(self, value: float | np.ndarray) -> float | np.ndarray:
        raw = self.center + self.spread * np.asarray(value, dtype=float)
        result = self._mixture_cdf(raw) if self.model == "normal_mixture_2" else self._frozen().cdf(raw)
        return float(result) if np.ndim(value) == 0 else np.asarray(result)

    def logpdf(self, value: float | np.ndarray) -> float | np.ndarray:
        raw = self.center + self.spread * np.asarray(value, dtype=float)
        if self.model == "normal_mixture_2":
            p = self.parameters
            pieces = np.stack((
                math.log(p["weight_1"]) + norm.logpdf(raw, p["mean_1"], p["sigma_1"]),
                math.log(p["weight_2"]) + norm.logpdf(raw, p["mean_2"], p["sigma_2"]),
            ))
            result = logsumexp(pieces, axis=0) + math.log(self.spread)
        else:
            result = self._frozen().logpdf(raw) + math.log(self.spread)
        return float(result) if np.ndim(value) == 0 else np.asarray(result)

    def ppf(self, probability: float | np.ndarray) -> float | np.ndarray:
        q = np.asarray(probability, dtype=float)
        if not np.isfinite(q).all() or (q <= 0).any() or (q >= 1).any():
            raise ValueError("Probabilities must be finite and strictly between zero and one")
        if self.model == "normal_mixture_2":
            raw = np.asarray([self._mixture_ppf(float(item)) for item in q.flat]).reshape(q.shape)
        else:
            raw = np.asarray(self._frozen().ppf(q))
        answer = (raw - self.center) / self.spread
        if not np.isfinite(answer).all():
            raise FitError(f"{self.model}: nonfinite quantile")
        return float(answer) if q.ndim == 0 else answer

    def _mixture_ppf(self, probability: float) -> float:
        low = self.center - 8 * self.spread
        high = self.center + 8 * self.spread
        for _ in range(20):
            if self._mixture_cdf(np.asarray(low)) <= probability:
                break
            low -= 8 * self.spread
        for _ in range(20):
            if self._mixture_cdf(np.asarray(high)) >= probability:
                break
            high += 8 * self.spread
        if self._mixture_cdf(np.asarray(low)) > probability or self._mixture_cdf(np.asarray(high)) < probability:
            raise FitError("Mixture quantile could not be bracketed")
        return float(brentq(lambda x: float(self._mixture_cdf(np.asarray(x))) - probability,
                            low, high))

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "parameters": self.parameters,
            "center": self.center,
            "spread": self.spread,
            "n_observations": self.n_observations,
            "log_likelihood": self.log_likelihood,
            "diagnostics": self.diagnostics,
        }


def _validated_sample(residuals: np.ndarray, config: FitConfig) -> np.ndarray:
    sample = np.asarray(residuals, dtype=float)
    if sample.ndim != 1 or len(sample) < config.min_observations or not np.isfinite(sample).all():
        raise FitError("Expected a one-dimensional finite historical sample of sufficient length")
    if np.std(sample) < 1e-8:
        raise FitError("Historical sample has negligible variance")
    return sample


def _mle_parameters(model: str, sample: np.ndarray, config: FitConfig) -> tuple[dict[str, float], dict]:
    median = float(np.clip(np.median(sample), -3, 3))
    log_scale = float(np.clip(math.log(np.std(sample)), -4, 3))
    skew = float(np.clip(np.mean(((sample - sample.mean()) / sample.std()) ** 3) / 10, -0.4, 0.4))
    if model == "student_t":
        starts = [[df, median, log_scale] for df in (4, 10, 40)]
        bounds = [(2.05, 200), (-3, 3), (-4, 3)]
    elif model == "ged":
        starts = [[beta, median, log_scale] for beta in (1, 2, 3)]
        bounds = [(0.4, 8), (-3, 3), (-4, 3)]
    elif model == "nig":
        starts = [[a, rho, median, log_scale] for a, rho in ((1, 0), (3, skew), (8, -skew))]
        bounds = [(0.1, 30), (-0.95, 0.95), (-3, 3), (-4, 3)]
    else:
        starts = [[p, a, rho, median, log_scale]
                  for p, a, rho in ((-0.5, 1, 0), (0.5, 3, skew), (1.5, 8, -skew))]
        bounds = [(-5, 5), (0.1, 30), (-0.95, 0.95), (-3, 3), (-4, 3)]

    def parameters(theta: np.ndarray) -> dict[str, float]:
        scale = math.exp(float(theta[-1]))
        loc = float(theta[-2])
        if model == "student_t":
            return {"df": float(theta[0]), "loc": loc, "scale": scale}
        if model == "ged":
            return {"beta": float(theta[0]), "loc": loc, "scale": scale}
        a, rho = float(theta[-4]), float(theta[-3])
        result = {"a": a, "b": a * rho, "loc": loc, "scale": scale}
        if model == "gh":
            result["p"] = float(theta[0])
        return result

    def objective(theta: np.ndarray) -> float:
        try:
            p = parameters(theta)
            if model == "student_t":
                values = t.logpdf(sample, p["df"], loc=p["loc"], scale=p["scale"])
            elif model == "ged":
                values = gennorm.logpdf(sample, p["beta"], loc=p["loc"], scale=p["scale"])
            elif model == "nig":
                values = norminvgauss.logpdf(sample, p["a"], p["b"], loc=p["loc"], scale=p["scale"])
            else:
                values = genhyperbolic.logpdf(sample, p["p"], p["a"], p["b"],
                                               loc=p["loc"], scale=p["scale"])
            total = -float(np.sum(values))
            return total if math.isfinite(total) else 1e100
        except (FloatingPointError, ValueError, OverflowError):
            return 1e100

    candidates = []
    messages = []
    for start in starts[:config.mle_starts]:
        fitted = minimize(objective, start, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": config.mle_max_iter})
        messages.append(str(fitted.message))
        if fitted.success and math.isfinite(fitted.fun) and fitted.fun < 1e99:
            candidates.append(fitted)
    if not candidates:
        raise FitError(f"{model}: no converged MLE start ({'; '.join(messages)})")
    best = min(candidates, key=lambda result: result.fun)
    return parameters(best.x), {
        "starts_attempted": len(messages),
        "converged_starts": len(candidates),
        "iterations": int(best.nit),
        "optimizer_message": str(best.message),
        "parameters_at_bound": int(sum(abs(value - low) < 1e-4 or abs(value - high) < 1e-4
                                       for value, (low, high) in zip(best.x, bounds))),
    }


def _mixture_parameters(sample: np.ndarray, config: FitConfig) -> tuple[dict[str, float], dict]:
    rng = np.random.default_rng(config.seed)
    variance = max(float(np.var(sample)), config.mixture_variance_floor)
    seeds = np.quantile(sample, [0.25, 0.75])
    candidates = []
    failure_reasons = []
    for start in range(config.mixture_starts):
        means = np.asarray(seeds, dtype=float).copy()
        if start:
            means += rng.normal(0, math.sqrt(variance) * 0.2, size=2)
        variances = np.full(2, variance)
        weights = np.full(2, 0.5)
        previous = -math.inf
        reason = "iteration limit"
        for iteration in range(1, config.mixture_max_iter + 1):
            terms = (np.log(weights)[None, :]
                     + norm.logpdf(sample[:, None], means[None, :], np.sqrt(variances)[None, :]))
            log_norm = logsumexp(terms, axis=1)
            if not np.isfinite(log_norm).all():
                reason = "nonfinite likelihood"
                break
            responsibilities = np.exp(terms - log_norm[:, None])
            counts = responsibilities.sum(axis=0)
            weights = counts / len(sample)
            if (weights < config.mixture_weight_floor).any():
                reason = "weight floor"
                break
            means = (responsibilities * sample[:, None]).sum(axis=0) / counts
            variances = np.maximum(
                (responsibilities * (sample[:, None] - means[None, :]) ** 2).sum(axis=0) / counts,
                config.mixture_variance_floor,
            )
            new_terms = (np.log(weights)[None, :]
                         + norm.logpdf(sample[:, None], means[None, :], np.sqrt(variances)[None, :]))
            likelihood = float(logsumexp(new_terms, axis=1).sum())
            if not math.isfinite(likelihood):
                reason = "nonfinite likelihood"
                break
            if iteration > 1 and likelihood < previous - 1e-8 * (1 + abs(previous)):
                reason = "likelihood decreased"
                break
            if iteration > 1 and abs(likelihood - previous) <= config.mixture_tolerance * (1 + abs(previous)):
                order = np.argsort(means)
                candidates.append((likelihood, weights[order], means[order], variances[order], iteration))
                reason = "converged"
                break
            previous = likelihood
        failure_reasons.append(reason)
    if not candidates:
        raise FitError(f"normal_mixture_2: no converged EM start ({', '.join(failure_reasons)})")
    _, weights, means, variances, iterations = max(candidates, key=lambda item: item[0])
    parameters = {
        "weight_1": float(weights[0]), "weight_2": float(weights[1]),
        "mean_1": float(means[0]), "mean_2": float(means[1]),
        "sigma_1": math.sqrt(float(variances[0])), "sigma_2": math.sqrt(float(variances[1])),
    }
    return parameters, {
        "starts_attempted": config.mixture_starts,
        "converged_starts": len(candidates),
        "iterations": iterations,
        "optimizer_message": "EM converged",
    }


def fit_distribution(model: str, residuals: np.ndarray, config: FitConfig) -> FittedDistribution:
    """Fit one candidate on caller-supplied past residuals; never silently substitute a law."""
    config.validate()
    if model not in config.models:
        raise ValueError(f"Model {model!r} is not enabled by the config")
    sample = _validated_sample(residuals, config)
    if model == "normal":
        parameters = {"loc": float(sample.mean()), "scale": float(sample.std())}
        diagnostics = {"starts_attempted": 0, "converged_starts": 0,
                       "iterations": 0, "optimizer_message": "closed-form Gaussian MLE"}
    elif model == "normal_mixture_2":
        parameters, diagnostics = _mixture_parameters(sample, config)
    else:
        parameters, diagnostics = _mle_parameters(model, sample, config)

    if model == "normal_mixture_2":
        center = sum(parameters[f"weight_{i}"] * parameters[f"mean_{i}"] for i in (1, 2))
        second = sum(parameters[f"weight_{i}"] *
                     (parameters[f"sigma_{i}"] ** 2 + parameters[f"mean_{i}"] ** 2)
                     for i in (1, 2))
        variance = second - center ** 2
    else:
        if model == "normal":
            rv = norm(loc=parameters["loc"], scale=parameters["scale"])
        elif model == "student_t":
            rv = t(parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
        elif model == "ged":
            rv = gennorm(parameters["beta"], loc=parameters["loc"], scale=parameters["scale"])
        elif model == "nig":
            rv = norminvgauss(parameters["a"], parameters["b"],
                              loc=parameters["loc"], scale=parameters["scale"])
        else:
            rv = genhyperbolic(parameters["p"], parameters["a"], parameters["b"],
                               loc=parameters["loc"], scale=parameters["scale"])
        center, variance = (float(value) for value in rv.stats(moments="mv"))
    if not math.isfinite(center) or not math.isfinite(variance) or variance <= 1e-12:
        raise FitError(f"{model}: fitted law has invalid moments")
    spread = math.sqrt(variance)
    result = FittedDistribution(model, parameters, center, spread, len(sample), 0.0, diagnostics)
    log_likelihood = float(np.sum(result.logpdf(sample)))
    if not math.isfinite(log_likelihood):
        raise FitError(f"{model}: nonfinite standardized log-likelihood")
    result = FittedDistribution(model, parameters, center, spread,
                                len(sample), log_likelihood, diagnostics)
    return result
