# On the Importance of Both Climate and Vegetation Evolution When Predicting Long-Term Wildfire Susceptibility 

This repository is based on the original implementation by [Trisung Dorji](https://github.com/Trisung-Dorji/Wildfire-Risk-Mapping), and extends it with several key modifications and updated datasets as part of our published study:

> **Ren, F.**, Tobinsky, N., Dorji, T., & Guibaud, A. (2025).  
> *On the importance of both climate and vegetation evolution when predicting long-term wildfire susceptibility*.  
> *International Journal of Wildland Fire*, 34, WF25092.  
> https://doi.org/10.1071/WF25092

---

## Overview

This project investigates the role of both climate change and vegetation dynamics in long-term wildfire susceptibility modeling. We build upon the original MaxEnt–GCN framework and extend the pipeline to support future scenario analysis, including CMIP6 climate projections and vegetation evolution.

The repository preserves the core structure of the original implementation while introducing additional preprocessing, scenario-specific analyses, and uncertainty assessment components.

---

## Key Enhancements and Modifications

The following extensions have been introduced on top of the original codebase:

- Integration of future climate projections from CMIP6 under SSP1-2.6, SSP2-4.5, and SSP5-8.5
- Sensitivity analysis separating:
  - climate-only change
  - combined climate and vegetation evolution
- Uncertainty analysis using Monte Carlo sampling within the GCN framework
- Additional preprocessing pipelines to generate machine-learning-ready inputs for downstream GCN modeling

### Newly Added and Modified Scripts

#### Python Notebooks
- **`SenClim.ipynb`**  
  Implements a climate-only scenario analysis to isolate the effect of climate change on wildfire susceptibility while keeping vegetation static.

- **`Maxent_GCN_Uncertainty.ipynb`**  
  Introduces Monte Carlo-based uncertainty estimation for the MaxEnt–GCN framework, enabling spatial uncertainty mapping and robustness assessment.

#### `R_scripts/` — Feature Engineering and GCN Input Preparation

- All R scripts that share filenames with Trisung’s original implementation have been **modified** to support updated spatial layers, future scenarios, and harmonized feature construction.
- Two new R Markdown scripts have been added:
  - **`MergeML.Rmd`**: Merges climate projections, topography, hydrology, and MaxEnt outputs into unified spatial feature layers for GCN input.
  - **`SensitivityAnalysisClimate.Rmd`**: Conducts sensitivity analyses under different climate scenarios to assess the stability and contribution of climate-driven features.

These scripts prepare spatially aligned, scenario-specific shapefiles used as direct inputs to the GCN model.

---

## Original Repository

The original implementation was developed by [Trisung Dorji](https://github.com/Trisung-Dorji/Wildfire-Risk-Mapping), our co-author and collaborator.  
All original credits and licensing terms are retained unless otherwise specified.

---

## Data Access

Due to the size of the original and derived datasets, we do not host them directly here. Instead, the primary climate inputs used in this project can be accessed from NASA's official data repository:

> **NASA NEX-GDDP-CMIP6 Dataset**  
> https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6  
> Global downscaled climate projections from CMIP6 GCMs (daily, 0.25° resolution, multiple SSP scenarios)

Additional access via **AWS Open Data Registry**:  
https://registry.opendata.aws/nex-gddp-cmip6/  
Data can be accessed directly through `s3://nex-gddp-cmip6`.

We specifically used projections from the **IPSL-CM6A-LR** model for both historical and future SSP scenarios.

Users may browse, download, or spatially subset the datasets using NASA’s THREDDS Data Server:  
https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/catalog.html

---

## Citation

If you use this repository or the associated data in your work, please cite:

```bibtex
@article{renImportanceBothClimate2025,
  title = {On the Importance of Both Climate and Vegetation Evolution When Predicting Long-Term Wildfire Susceptibility},
  author = {Ren, Feiyang and Tobinsky, Noah and Dorji, Trisung and Guibaud, Augustin},
  year = 2025,
  journal = {International Journal of Wildland Fire},
  volume = {34},
  number = {12},
  pages = {WF25092},
  issn = {1049-8001},
  doi = {10.1071/WF25092}
}
