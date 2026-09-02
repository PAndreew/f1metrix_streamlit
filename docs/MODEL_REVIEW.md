# Model and repository review

## What was actually in the original repository

The cloned `PAndreew/f1metrix_streamlit` repository contained a Streamlit presentation layer and a 2.1 MB SQLite file of fitted results. It did **not** contain the PyMC training script, source F1DB data, posterior samples, preprocessing rules, priors, or posterior-predictive checks. The original fit therefore was not reproducible from the public repository.

The saved `model_summary` also shows that the fit should not be published as converged. The worst constructor-year scale has `r_hat = 1.5859` and bulk ESS `7.1`; driver and team scale parameters also exceed 1.01. The UI nevertheless presented point rankings without surfacing this warning.

## Research checked

### Bell, Smith, Sabel & Jones (2016)

“Formula for success: Multilevel modelling of Formula One Driver and Constructor performance, 1950–2014,” *Journal of Quantitative Analysis in Sports* 12(2), 99–112, DOI [10.1515/jqas-2015-0050](https://doi.org/10.1515/jqas-2015-0050).

The paper's useful core is a cross-classified model of driver, team and team-year effects. It excludes Indianapolis 500 rounds, applies a common points function, rankit-transforms the result, and fits Normal random effects. It also explores variance functions for era, weather and circuit type. Its claim that technical failures are automatically apportioned to teams is only safe with enough teammate/team-year replication; a particular driver's idiosyncratic reliability can still enter that driver's residual.

### Andrew Phillips (f1metrics, 2019)

[A new f1metrics model](https://f1metrics.wordpress.com/2019/09/10/a-new-f1metrics-model/) adds domain knowledge missing from a static career effect:

- a shared age curve, with a broad plateau around 26–35;
- recent experience, defined as participation in the previous four seasons;
- a customer-car penalty for 1950–1980;
- robust scoring that extends points through the field and half-weights season extremes.

Phillips' manually classified non-driver DNFs are valuable but are not published as a reusable dataset. F1DB retirement reasons are used here as a documented, conservative substitute.

## Problems in the inherited result model/UI

1. **Non-convergence:** several reported R-hat and ESS values are unacceptable.
2. **Grid is post-treatment:** the fitted `beta_grid` controls for qualifying position. Grid is itself produced by driver and car ability, so conditioning on it removes part of the effects the site claims to estimate.
3. **Technical DNFs:** the article admits they are not handled, and ordinary Gaussian residuals can assign broken-car outcomes to drivers.
4. **Customer effect unidentified:** the saved customer coefficient is `-0.077 ± 0.454`; this does not support a useful claimed adjustment.
5. **Fragile likelihood:** a Gaussian observation model is sensitive to unusual race outcomes. Phillips explicitly identified this failure mode.
6. **No reproducibility or validation:** source data version, preprocessing, priors, posterior samples, random seeds and predictive checks were absent.
7. **Hard-coded years:** multiple Streamlit queries and controls explicitly name 2024/2025.
8. **Presentation coupling:** SQL, plotting, article parsing and page rendering live in one 700-line file. A model refresh requires replacing a database beneath Streamlit caches.
9. **Public arbitrary SQL:** checking only that text starts with `SELECT` is not an appropriate public query API and allows expensive requests.
10. **Unsafe article HTML:** acceptable only while posts remain owner-authored and deployment-controlled.

## v2 decisions

The replacement uses a Student-t likelihood over within-race Normal order scores and partially pooled driver, constructor and constructor-season effects. It excludes Indianapolis rounds and technical/ambiguous retirements, retains driver-error retirements, removes grid, and adds constrained shared age and recent-experience curves. Conservative driver rank uses the lower 3% posterior quantile.

This is a better baseline, not a final scientific result. Before treating rankings as publication-quality:

- run two or more NUTS chains and require R-hat ≤ 1.01, adequate ESS and zero/understood divergences;
- perform posterior predictive checks by era, finishing position, constructor and retirement class;
- use held-out future-race and held-out-teammate comparisons against simpler baselines;
- sensitivity-test retirement mappings and priors;
- curate entrant-level works/customer data before adding that effect;
- consider separate wet/street effects only when weather coverage is auditable.

The daily VPS update uses ADVI because the server has two cores and 4 GB RAM. Those updates are operational estimates and explicitly lack NUTS convergence diagnostics. Periodic NUTS fits should replace them after validation on a larger machine or during a maintenance window.
