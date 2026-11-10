"""Tiny real-PyMC wiring test, not evidence of model convergence or calibration.
Runs on hosted CI with model requirements; skipped in lightweight local test runs.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pm = pytest.importorskip('pymc')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
from fit import build_model, posterior_matrix


def test_real_nuts_and_posterior_dimensions(tmp_path):
    observations = pd.DataFrame({
        'driver_idx': [0, 1, 0, 1, 0, 1],
        'constructor_idx': [0, 1, 0, 1, 0, 1],
        'constructor_year_idx': [0, 1, 0, 1, 0, 1],
        'age': [25., 30., 25., 30., 26., 31.],
        'experience': [1, 3, 1, 3, 2, 4],
        'rankit': [.7, -.7, .4, -.4, -.2, .2],
    })
    data = SimpleNamespace(observations=observations, driver_ids=['a', 'b'],
        constructor_ids=['one', 'two'], constructor_year_ids=['one:2020', 'two:2020'])
    model = build_model(data)
    with model:
        idata = pm.sample(draws=12, tune=12, chains=2, cores=1, target_accept=.85,
            progressbar=False, random_seed=[4, 5], compute_convergence_checks=False)
    assert posterior_matrix(idata, 'driver_skill').shape == (24, 2)
    assert posterior_matrix(idata, 'mu').shape == (24, 6)
    assert np.isfinite(posterior_matrix(idata, 'mu')).all()
    np.testing.assert_allclose(posterior_matrix(idata, 'driver_skill').sum(axis=1), 0, atol=1e-10)
    path = tmp_path / 'posterior.nc'
    idata.to_netcdf(path, engine='h5netcdf')
    assert path.stat().st_size > 0
