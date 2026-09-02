import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "model"))
from data import recent_experience


def test_recent_experience_looks_back_four_seasons_and_decays():
    index = pd.MultiIndex.from_tuples(
        [("driver-a", 2010), ("driver-a", 2011), ("driver-a", 2013), ("driver-a", 2017), ("driver-a", 2018)],
        names=["driver_id", "year"],
    )
    years = pd.Series(index.get_level_values("year"), index=index)
    assert recent_experience(years).tolist() == [0, 1, 2, 1, 1]
