"""Load and prepare F1DB race results for the Bayesian model."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

# Outcomes that primarily describe driver error. Technical and ambiguous retirements
# are omitted: the model estimates pace conditional on the car remaining healthy.
DRIVER_RETIREMENTS = {
    "Accident", "Collision", "Spun off", "Spin", "Fatal accident",
    "Fatal collision", "Caused collision with Trulli", "Accident damage",
    "Collision damage", "Accident on formation lap",
}


@dataclass(frozen=True)
class ModelData:
    observations: pd.DataFrame
    drivers: pd.DataFrame
    constructors: pd.DataFrame
    driver_ids: list[str]
    constructor_ids: list[str]
    constructor_year_ids: list[str]


def recent_experience(years: pd.Series) -> pd.Series:
    """Number of the preceding four seasons in which each driver raced."""
    seen: dict[str, set[int]] = {}
    values: list[int] = []
    for driver, year in zip(years.index.get_level_values(0), years.astype(int)):
        prior = seen.setdefault(driver, set())
        values.append(sum((year - offset) in prior for offset in range(1, 5)))
        prior.add(year)
    return pd.Series(values, index=years.index, dtype="int64")


def load_model_data(database: str | Path, through_year: int | None = None, before_date: str | None = None) -> ModelData:
    conn = sqlite3.connect(f"file:{Path(database).resolve()}?mode=ro", uri=True)
    where_year = "AND r.year <= ?" if through_year else ""
    params = (through_year,) if through_year else ()
    if before_date:
        where_year += " AND r.date < ?"
        params += (before_date,)
    results = pd.read_sql_query(
        f"""
        SELECT rr.race_id, r.year, r.round, r.date, r.official_name,
               r.grand_prix_id, r.circuit_type, rr.position_display_order AS position,
               rr.driver_id, rr.constructor_id, rr.grid_position_number AS grid,
               rr.reason_retired, rr.laps, rr.shared_car,
               d.first_name, d.last_name, d.date_of_birth,
               d.nationality_country_id, c.name AS constructor_name
          FROM race_result rr
          JOIN race r ON r.id = rr.race_id
          JOIN driver d ON d.id = rr.driver_id
          JOIN constructor c ON c.id = rr.constructor_id
         WHERE date(r.date) <= date('now')
           AND r.grand_prix_id != 'indianapolis'
           {where_year}
         ORDER BY r.date, rr.position_display_order
        """,
        conn,
        params=params,
    )
    drivers = pd.read_sql_query(
        "SELECT id, first_name, last_name, name, nationality_country_id, date_of_birth FROM driver",
        conn,
    )
    constructors = pd.read_sql_query("SELECT id, name, full_name, country_id FROM constructor", conn)
    conn.close()

    results["reason_retired"] = results["reason_retired"].fillna("")
    results["included"] = (results["reason_retired"] == "") | results["reason_retired"].isin(DRIVER_RETIREMENTS)
    results["included"] &= results["shared_car"].fillna(0).eq(0)
    results["field_size"] = results.groupby("race_id")["driver_id"].transform("size")
    # Best finisher gets the largest expected Normal order statistic.
    percentile = (results["field_size"] - results["position"] + 0.5) / results["field_size"]
    results["rankit"] = norm.ppf(percentile.clip(0.001, 0.999))
    results["age"] = (
        pd.to_datetime(results["date"]) - pd.to_datetime(results["date_of_birth"])
    ).dt.days / 365.2425

    # Recent experience is season-based and intentionally decays after an absence.
    seasons = (
        results[["driver_id", "year"]]
        .drop_duplicates()
        .sort_values(["driver_id", "year"])
        .set_index(["driver_id", "year"])
    )
    year_series = pd.Series(seasons.index.get_level_values("year"), index=seasons.index)
    seasons["experience"] = recent_experience(year_series)
    results = results.merge(seasons.reset_index(), on=["driver_id", "year"], how="left")

    observations = results.loc[results["included"]].copy().reset_index(drop=True)
    if observations.empty:
        raise ValueError("No usable race observations before the requested cutoff")
    driver_ids = sorted(observations["driver_id"].unique())
    constructor_ids = sorted(observations["constructor_id"].unique())
    observations["constructor_year_id"] = observations["constructor_id"] + ":" + observations["year"].astype(str)
    constructor_year_ids = sorted(observations["constructor_year_id"].unique())
    observations["driver_idx"] = pd.Categorical(observations["driver_id"], driver_ids).codes
    observations["constructor_idx"] = pd.Categorical(observations["constructor_id"], constructor_ids).codes
    observations["constructor_year_idx"] = pd.Categorical(
        observations["constructor_year_id"], constructor_year_ids
    ).codes

    return ModelData(observations, drivers, constructors, driver_ids, constructor_ids, constructor_year_ids)
