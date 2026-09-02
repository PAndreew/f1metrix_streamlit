#!/usr/bin/env python3
"""Fit the F1 Metrix hierarchical model and publish a compact JSON snapshot."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data import ModelData, load_model_data


def build_model(data: ModelData):
    import pymc as pm
    import pytensor.tensor as pt

    obs = data.observations
    coords = {
        "observation": np.arange(len(obs)),
        "driver": data.driver_ids,
        "constructor": data.constructor_ids,
        "constructor_year": data.constructor_year_ids,
        "experience_level": np.arange(1, 5),
    }
    with pm.Model(coords=coords) as model:
        driver_idx = pm.Data("driver_idx", obs.driver_idx, dims="observation")
        constructor_idx = pm.Data("constructor_idx", obs.constructor_idx, dims="observation")
        constructor_year_idx = pm.Data(
            "constructor_year_idx", obs.constructor_year_idx, dims="observation"
        )
        age = pm.Data("age", obs.age.to_numpy(), dims="observation")
        experience = pm.Data("experience", obs.experience.to_numpy(), dims="observation")

        intercept = pm.Normal("intercept", 0, 0.25)
        sigma_driver = pm.HalfNormal("sigma_driver", 0.4)
        sigma_constructor = pm.HalfNormal("sigma_constructor", 0.6)
        sigma_constructor_year = pm.HalfNormal("sigma_constructor_year", 0.5)
        driver_raw = pm.Normal("driver_raw", 0, 1, dims="driver")
        constructor_raw = pm.Normal("constructor_raw", 0, 1, dims="constructor")
        constructor_year_raw = pm.Normal("constructor_year_raw", 0, 1, dims="constructor_year")
        driver_skill = pm.Deterministic(
            "driver_skill", sigma_driver * (driver_raw - pt.mean(driver_raw)), dims="driver"
        )
        constructor_skill = pm.Deterministic(
            "constructor_skill",
            sigma_constructor * (constructor_raw - pt.mean(constructor_raw)),
            dims="constructor",
        )
        constructor_year_skill = pm.Deterministic(
            "constructor_year_skill",
            sigma_constructor_year * (constructor_year_raw - pt.mean(constructor_year_raw)),
            dims="constructor_year",
        )

        # A shared career curve avoids the severe driver-age confounding caused by
        # fitting an unconstrained slope for every driver's short career.
        age_peak = pm.TruncatedNormal("age_peak", mu=30, sigma=3, lower=22, upper=38)
        age_decline = pm.HalfNormal("age_decline", 0.35)
        age_effect = -age_decline * pt.square((age - age_peak) / 10)

        # Recent experience is monotonic and saturates after four active seasons.
        experience_steps = pm.HalfNormal("experience_steps", 0.12, dims="experience_level")
        experience_curve = pt.concatenate([pt.zeros(1), pt.cumsum(experience_steps)])
        experience_effect = experience_curve[experience]

        mu = (
            intercept
            + driver_skill[driver_idx]
            + constructor_skill[constructor_idx]
            + constructor_year_skill[constructor_year_idx]
            + age_effect
            + experience_effect
        )
        pm.Deterministic("mu", mu, dims="observation")
        nu = pm.Exponential("nu_minus_two", 1 / 15) + 2
        sigma = pm.HalfNormal("sigma", 0.7)
        pm.StudentT("rankit", nu=nu, mu=mu, sigma=sigma, observed=obs.rankit, dims="observation")
    return model


def posterior_matrix(idata, variable: str) -> np.ndarray:
    values = idata.posterior[variable].stack(sample=("chain", "draw"))
    other = [d for d in values.dims if d != "sample"]
    return values.transpose("sample", *other).values


def interval(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return tuple(np.quantile(values, q, axis=0) for q in (0.5, 0.03, 0.97))


def export_snapshot(data: ModelData, idata, source_db: Path, output: Path, release: str) -> None:
    driver_samples = posterior_matrix(idata, "driver_skill")
    constructor_samples = posterior_matrix(idata, "constructor_skill")
    cy_samples = posterior_matrix(idata, "constructor_year_skill")
    driver_mid, driver_low, driver_high = interval(driver_samples)

    obs = data.observations
    counts = obs.groupby("driver_id").agg(races=("race_id", "nunique"), first_year=("year", "min"), last_year=("year", "max"))
    dmeta = data.drivers.set_index("id")
    drivers = []
    order = np.argsort(-driver_low)
    ranks = np.empty(len(order), dtype=int)
    ranks[order] = np.arange(1, len(order) + 1)
    for i, driver_id in enumerate(data.driver_ids):
        meta, count = dmeta.loc[driver_id], counts.loc[driver_id]
        drivers.append({
            "id": driver_id, "name": f"{meta.first_name} {meta.last_name}",
            "nationality": meta.nationality_country_id, "races": int(count.races),
            "firstYear": int(count.first_year), "lastYear": int(count.last_year),
            "skill": round(float(driver_mid[i]), 4), "low": round(float(driver_low[i]), 4),
            "high": round(float(driver_high[i]), 4), "rank": int(ranks[i]),
        })

    # Driver-season values combine baseline talent with the shared age/experience curve.
    age_peak = posterior_matrix(idata, "age_peak")[:, 0] if posterior_matrix(idata, "age_peak").ndim > 1 else posterior_matrix(idata, "age_peak")
    age_decline = posterior_matrix(idata, "age_decline")[:, 0] if posterior_matrix(idata, "age_decline").ndim > 1 else posterior_matrix(idata, "age_decline")
    exp_steps = posterior_matrix(idata, "experience_steps")
    exp_curve = np.concatenate([np.zeros((len(exp_steps), 1)), np.cumsum(exp_steps, axis=1)], axis=1)
    season_rows = obs.groupby(["driver_id", "year"], as_index=False).agg(age=("age", "mean"), experience=("experience", "first"))
    driver_lookup = {value: i for i, value in enumerate(data.driver_ids)}
    yearly = []
    for row in season_rows.itertuples(index=False):
        samples = driver_samples[:, driver_lookup[row.driver_id]]
        samples = samples - age_decline * ((row.age - age_peak) / 10) ** 2 + exp_curve[:, int(row.experience)]
        mid, low, high = np.quantile(samples, [0.5, 0.03, 0.97])
        yearly.append({"driverId": row.driver_id, "year": int(row.year), "score": round(float(mid), 4), "low": round(float(low), 4), "high": round(float(high), 4)})
    for year in sorted({x["year"] for x in yearly}):
        rows = sorted((x for x in yearly if x["year"] == year), key=lambda x: -x["score"])
        for rank, row in enumerate(rows, 1): row["rank"] = rank

    cmeta = data.constructors.set_index("id")
    teams = []
    for i, key in enumerate(data.constructor_year_ids):
        constructor_id, year = key.rsplit(":", 1)
        combined = constructor_samples[:, data.constructor_ids.index(constructor_id)] + cy_samples[:, i]
        score, low, high = np.quantile(combined, [0.5, 0.03, 0.97])
        teams.append({"id": constructor_id, "name": cmeta.loc[constructor_id]["name"], "year": int(year),
                      "score": round(float(score), 4), "low": round(float(low), 4),
                      "high": round(float(high), 4)})
    for year in sorted({x["year"] for x in teams}):
        rows = sorted((x for x in teams if x["year"] == year), key=lambda x: -x["score"])
        for rank, row in enumerate(rows, 1): row["rank"] = rank

    mu = idata.posterior["mu"].mean(("chain", "draw")).values
    poe = obs.assign(poe=obs.rankit.to_numpy() - mu)
    latest_ids = set(obs.drop_duplicates("race_id").sort_values("date").tail(40).race_id)
    race_rows = poe[poe.race_id.isin(latest_ids)]
    races = []
    for race_id, group in race_rows.groupby("race_id", sort=False):
        first = group.iloc[0]
        races.append({"id": int(race_id), "year": int(first.year), "round": int(first["round"]),
                      "date": first.date, "name": first.official_name,
                      "results": [{"driverId": r.driver_id, "position": int(r.position), "poe": round(float(r.poe), 4)} for r in group.itertuples()]})

    diagnostics = {}
    try:
        import arviz as az
        if idata.posterior.sizes.get("chain", 1) < 2:
            raise ValueError("fewer than two chains")
        summary = az.summary(idata, var_names=["sigma_driver", "sigma_constructor", "sigma_constructor_year", "sigma", "age_peak", "age_decline"])
        diagnostics = {"maxRhat": round(float(summary.r_hat.max()), 4), "minEssBulk": round(float(summary.ess_bulk.min()), 1)}
        if "sample_stats" in idata and "diverging" in idata.sample_stats:
            diagnostics["divergences"] = int(idata.sample_stats.diverging.sum())
    except Exception:
        diagnostics = {"note": "Approximate inference does not provide NUTS convergence diagnostics."}

    last = obs.sort_values("date").iloc[-1]
    payload = {"metadata": {"generatedAt": datetime.now(UTC).isoformat(), "sourceRelease": release,
                "lastRace": last.official_name, "lastRaceDate": last.date, "observations": len(obs),
                "model": "hierarchical Student-t v2", "diagnostics": diagnostics},
               "drivers": drivers, "driverYears": yearly, "teams": teams, "races": races}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, separators=(",", ":"))
        temporary = Path(handle.name)
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", default="data/model-output.json", type=Path)
    parser.add_argument("--artifact", default="model/artifacts/posterior.nc", type=Path)
    parser.add_argument("--release", default="unknown")
    parser.add_argument("--method", choices=("nuts", "advi"), default="nuts")
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--tune", type=int, default=1200)
    parser.add_argument("--advi-iterations", type=int, default=60000)
    parser.add_argument("--through-year", type=int)
    args = parser.parse_args()

    import arviz as az
    import pymc as pm
    data = load_model_data(args.database, args.through_year)
    model = build_model(data)
    with model:
        if args.method == "nuts":
            idata = pm.sample(draws=args.draws, tune=args.tune, chains=2, cores=1,
                              target_accept=0.92, random_seed=[1949, 2024], return_inferencedata=True)
        else:
            approximation = pm.fit(args.advi_iterations, method="advi", random_seed=1949,
                                   callbacks=[pm.callbacks.CheckParametersConvergence(tolerance=0.001)])
            idata = approximation.sample(args.draws, random_seed=2024, return_inferencedata=True)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    az.to_netcdf(idata, args.artifact)
    export_snapshot(data, idata, args.database, args.output, args.release)


if __name__ == "__main__":
    main()
