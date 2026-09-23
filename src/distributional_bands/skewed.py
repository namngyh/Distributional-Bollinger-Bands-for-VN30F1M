"""Two-piece skew extensions of symmetric Student-t and GED laws.

The left and right scales are ``scale * exp(-skew)`` and
``scale * exp(skew)``. Zero skew exactly recovers the symmetric parent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln
from scipy.stats import gennorm, t


@dataclass(frozen=True)
class TwoPieceLaw:
    family: str
    shape: float
    skew: float
    loc: float = 0.0
    scale: float = 1.0

    def _base(self):
        if self.family == "student_t":
            if self.shape <= 2:
                raise ValueError("Student-t requires df > 2 for finite variance")
            return t(self.shape)
        if self.family == "ged":
            if self.shape <= 0:
                raise ValueError("GED shape must be positive")
            return gennorm(self.shape)
        raise ValueError("Unknown two-piece parent family")

    def _scales(self) -> tuple[float, float]:
        if self.scale <= 0 or not all(map(math.isfinite, (self.shape, self.skew, self.loc, self.scale))):
            raise ValueError("Two-piece parameters must be finite and scale positive")
        return self.scale * math.exp(-self.skew), self.scale * math.exp(self.skew)

    def logpdf(self, value: float | np.ndarray) -> float | np.ndarray:
        left, right = self._scales()
        x = np.asarray(value, dtype=float)
        local_scale = np.where(x < self.loc, left, right)
        answer = math.log(2 / (left + right)) + self._base().logpdf((x - self.loc) / local_scale)
        return float(answer) if x.ndim == 0 else answer

    def cdf(self, value: float | np.ndarray) -> float | np.ndarray:
        left, right = self._scales()
        x = np.asarray(value, dtype=float)
        base = self._base()
        below = 2 * left / (left + right) * base.cdf((x - self.loc) / left)
        above = left / (left + right) + 2 * right / (left + right) * (
            base.cdf((x - self.loc) / right) - 0.5)
        answer = np.where(x < self.loc, below, above)
        return float(answer) if x.ndim == 0 else answer

    def ppf(self, probability: float | np.ndarray) -> float | np.ndarray:
        left, right = self._scales()
        q = np.asarray(probability, dtype=float)
        if not np.isfinite(q).all() or (q <= 0).any() or (q >= 1).any():
            raise ValueError("Probabilities must lie strictly between zero and one")
        base = self._base()
        left_mass = left / (left + right)
        safe_left = np.minimum(q * (left + right) / (2 * left), 0.5)
        safe_right = np.maximum(0.5 + (q - left_mass) * (left + right) / (2 * right), 0.5)
        answer = np.where(q < left_mass,
                          self.loc + left * base.ppf(safe_left),
                          self.loc + right * base.ppf(safe_right))
        return float(answer) if q.ndim == 0 else answer

    def stats(self, moments: str = "mv") -> tuple[float, float]:
        if moments != "mv":
            raise ValueError("Only mean and variance are supported")
        left, right = self._scales()
        if self.family == "student_t":
            absolute_first = math.exp(0.5 * math.log(self.shape)
                                      + gammaln((self.shape - 1) / 2)
                                      - 0.5 * math.log(math.pi) - gammaln(self.shape / 2))
            second = self.shape / (self.shape - 2)
        else:
            absolute_first = math.exp(gammaln(2 / self.shape) - gammaln(1 / self.shape))
            second = math.exp(gammaln(3 / self.shape) - gammaln(1 / self.shape))
        shift = absolute_first * (right - left)
        second_about_loc = second * (left ** 3 + right ** 3) / (left + right)
        return self.loc + shift, second_about_loc - shift ** 2
