![GitHub repo size](https://img.shields.io/github/repo-size/JanaRobbins/mt-st-helens-xdem-coreg-conda?style=plastic)  ![GitHub last commit](https://img.shields.io/github/last-commit/JanaRobbins/mt-st-helens-xdem-coreg-conda?style=plastic) ![GitHub watchers](https://img.shields.io/github/watchers/JanaRobbins/mt-st-helens-xdem-coreg-conda?style=plastic) ![GitHub repo directory count](https://img.shields.io/github/directory-file-count/JanaRobbins/mt-st-helens-xdem-coreg-conda?style=plastic) ![](https://komarev.com/ghpvc/?username=JanaRobbins&style=plastic&label=Profile+views&color=ff69b4)

# xDEM Co-registration for Mount St. Helens crater glacier and lava dome analysis

This project applies DEM co-registration and uncertainty assessment for Mount St. Helens crater using the `xDEM` Python library.

## Input data

Place the following files inside the `data/` folder:

- `dem_1984.tif` - reference DEM
- `dem_2008.tif` - DEM to align
- `dem_2023.tif` - DEM to align
- `stable_mask.tif` - stable terrain mask (`1 = stable`, `0 = unstable`)

## Workflow

1. Align DEMs to the 1984 reference grid  
2. Apply stable terrain mask  
3. Perform Nuth & Kääb co-registration  
4. Save corrected DEMs  
5. Export shifts and NMAD statistics

## Instalation

Create the Conda environment from the `environment.yml` file:

```bash
conda env create -f environment.yml
conda activate xdem_envi
```

## File paths to edit

Before running the script, update these lines in `coregister_dems.py` if your file names are different:

```python
REF_PATH = DATA_DIR / "dem_1984.tif"
DEM_PATHS = [
    DATA_DIR / "dem_2008.tif",
    DATA_DIR / "dem_2023.tif",
]
MASK_PATH = DATA_DIR / "stable_mask.tif"
```

## Outputs

- `dem_2008_coreg.tif`
- `dem_2023_coreg.tif`
- `coreg_stats.csv`

## Results

Co-registration reduced elevation differences on stable terrain:

| DEM  | NMAD Before | NMAD After | Shift X  | Shift Y | Shift Z   |
|------|-------------|------------|----------|---------|-----------|
| 2008 | 2.206073 m  | 2.158566 m |  -0.43 m | -3.16 m |  -4.49 m  |  
| 2023 | 2.589211 m  | 1.876958 m |   +0.70   | -6.83 m | -24.46 m  |


## Credits

The code was created during the study of the module Photogrammetry and Advance Image Analysis in the School of Geography and Environmental Sciences in the [University of Ulster](https://www.ulster.ac.uk/courses/202324/geographic-information-systems-30225).  


## Licence

A MIT licence was used. You can contact author at - janarobbins.gis@gmail.com 
