"""
Glicko-2 rating system for tournament rankings.

Each skill has three values:
  mu (μ)     — rating (default 1500, higher = better)
  rd (φ)     — rating deviation (uncertainty, starts at 350)
  sigma (σ)  — volatility (consistency, starts at 0.06)

After a tournament, pairwise matchups between all skills
update these values. New skills have high RD (uncertain),
veterans have low RD (stable).

Reference: http://www.glicko.net/glicko/glicko2.pdf
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Glicko-2 constants
MU_DEFAULT = 1500.0
RD_DEFAULT = 350.0
SIGMA_DEFAULT = 0.06
TAU = 0.5  # system constant constraining volatility change
EPSILON = 0.000001  # convergence tolerance

# Scale factor between Glicko-1 and Glicko-2 internal scales.
# Glicko-2 operates on a compressed scale; this converts between the two.
GLICKO2_SCALE = 173.7178


@dataclass
class Rating:
    """A player's Glicko-2 rating state."""
    mu: float = MU_DEFAULT
    rd: float = RD_DEFAULT
    sigma: float = SIGMA_DEFAULT

    @property
    def glicko2_mu(self) -> float:
        """Convert mu to the Glicko-2 internal scale (Step 2 of the paper)."""
        return (self.mu - MU_DEFAULT) / GLICKO2_SCALE

    @property
    def glicko2_phi(self) -> float:
        """Convert RD to the Glicko-2 internal scale (Step 2 of the paper)."""
        return self.rd / GLICKO2_SCALE


def _g(phi: float) -> float:
    """Glicko-2 g function — reduces impact of opponent with high uncertainty.

    g(φ) = 1 / sqrt(1 + 3φ²/π²)
    """
    return 1.0 / math.sqrt(1.0 + 3.0 * phi**2 / math.pi**2)


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    """Expected score of player with rating mu against opponent mu_j.

    E(μ, μⱼ, φⱼ) = 1 / (1 + exp(-g(φⱼ)(μ - μⱼ)))
    """
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _compute_v(mu: float, opponents: list[tuple[float, float]]) -> float:
    """Estimated variance of the player's rating based on game outcomes (Step 3).

    v = [Σ g(φⱼ)² · E(μ,μⱼ,φⱼ) · (1 - E(μ,μⱼ,φⱼ))]⁻¹
    """
    total = 0.0
    for mu_j, phi_j in opponents:
        g_val = _g(phi_j)
        e_val = _E(mu, mu_j, phi_j)
        total += g_val**2 * e_val * (1.0 - e_val)
    if total == 0:
        return float("inf")
    return 1.0 / total


def _compute_delta(
    mu: float,
    opponents: list[tuple[float, float]],
    scores: list[float],
    v: float,
) -> float:
    """Estimated improvement in rating (Step 4).

    Δ = v · Σ g(φⱼ) · (sⱼ - E(μ, μⱼ, φⱼ))
    """
    total = 0.0
    for (mu_j, phi_j), s_j in zip(opponents, scores):
        total += _g(phi_j) * (s_j - _E(mu, mu_j, phi_j))
    return v * total


def _new_sigma(sigma: float, phi: float, v: float, delta: float) -> float:
    """Compute new volatility using the Illinois algorithm (Step 5 of the paper).

    This is the iterative procedure described in Section 5.4 of Glickman's paper.
    It finds σ' such that f(ln(σ'²)) = 0 via a modified regula falsi (Illinois)
    method, which is guaranteed to converge.
    """
    a = math.log(sigma**2)

    def f(x: float) -> float:
        ex = math.exp(x)
        d2 = delta**2
        p2 = phi**2
        num = ex * (d2 - p2 - v - ex)
        denom = 2.0 * (p2 + v + ex) ** 2
        return num / denom - (x - a) / TAU**2

    # Step 5.1: Set initial bracket [A, B]
    A = a
    if delta**2 > phi**2 + v:
        B = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU

    # Step 5.2: Iterate until convergence
    fA = f(A)
    fB = f(B)
    while abs(B - A) > EPSILON:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A = B
            fA = fB
        else:
            fA = fA / 2.0
        B = C
        fB = fC

    return math.exp(A / 2.0)


def update_rating(
    rating: Rating,
    opponents: list[tuple[float, float]],
    scores: list[float],
) -> Rating:
    """Full Glicko-2 rating update for one player after a rating period.

    Implements Steps 2-8 of the Glicko-2 paper.

    Args:
        rating: Current rating of the player.
        opponents: List of (mu_glicko2, phi_glicko2) for each opponent faced.
        scores: List of match outcomes (1.0 = win, 0.5 = draw, 0.0 = loss).

    Returns:
        Updated Rating on the original Glicko-1 scale.
    """
    # Step 2: Convert to Glicko-2 scale
    mu = rating.glicko2_mu
    phi = rating.glicko2_phi
    sigma = rating.sigma

    if not opponents:
        # No games in this period: only increase RD (Step 6 with no update)
        new_phi = math.sqrt(phi**2 + sigma**2)
        return Rating(
            mu=rating.mu,
            rd=min(new_phi * GLICKO2_SCALE, RD_DEFAULT),
            sigma=sigma,
        )

    # Step 3: Compute estimated variance v
    v = _compute_v(mu, opponents)

    # Step 4: Compute estimated improvement delta
    delta = _compute_delta(mu, opponents, scores, v)

    # Step 5: Compute new volatility sigma'
    new_sigma = _new_sigma(sigma, phi, v, delta)

    # Step 6: Update phi to phi* (pre-rating period value)
    phi_star = math.sqrt(phi**2 + new_sigma**2)

    # Step 7: Update phi and mu
    new_phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
    new_mu = mu + new_phi**2 * sum(
        _g(phi_j) * (s - _E(mu, mu_j, phi_j))
        for (mu_j, phi_j), s in zip(opponents, scores)
    )

    # Step 8: Convert back to Glicko-1 scale
    return Rating(
        mu=new_mu * GLICKO2_SCALE + MU_DEFAULT,
        rd=new_phi * GLICKO2_SCALE,
        sigma=new_sigma,
    )


def update_tournament_ratings(
    ratings: dict[str, Rating],
    scores: dict[str, float],
) -> dict[str, Rating]:
    """Update all ratings after a tournament round-robin.

    Each skill is matched pairwise against every other skill. The outcome
    is determined by comparing their tournament average scores:
      - If A scored more than B by > 0.02, A wins (1.0) and B loses (0.0).
      - If the difference is within 0.02, both get a draw (0.5).

    Args:
        ratings: {skill_id: Rating} for all participants.
        scores: {skill_id: tournament_avg_score} on 0-1 scale.

    Returns:
        Updated {skill_id: Rating} after the Glicko-2 update.
    """
    skill_ids = list(scores.keys())
    new_ratings: dict[str, Rating] = {}

    for sid in skill_ids:
        my_score = scores[sid]
        my_rating = ratings.get(sid, Rating())

        opponents: list[tuple[float, float]] = []
        match_scores: list[float] = []

        for oid in skill_ids:
            if oid == sid:
                continue
            opp_rating = ratings.get(oid, Rating())
            opponents.append((opp_rating.glicko2_mu, opp_rating.glicko2_phi))

            # Pairwise outcome based on score difference
            diff = my_score - scores[oid]
            if diff > 0.02:
                match_scores.append(1.0)
            elif diff < -0.02:
                match_scores.append(0.0)
            else:
                match_scores.append(0.5)

        new_ratings[sid] = update_rating(my_rating, opponents, match_scores)

    return new_ratings


def decay_inactive(rating: Rating) -> Rating:
    """Increase RD for skills that didn't compete in a rating period.

    Call once per missed tournament week. RD grows (more uncertain)
    but is capped at RD_DEFAULT.
    """
    return update_rating(rating, [], [])
