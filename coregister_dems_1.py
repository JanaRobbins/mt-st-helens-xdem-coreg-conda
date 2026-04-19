import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
import xdem
import geoutils as gu


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

REF_PATH = DATA_DIR / "dem_1984.tif"
DEM_PATHS = [
    DATA_DIR / "dem_2008.tif",
    DATA_DIR / "dem_2023.tif",
]
MASK_PATH = DATA_DIR / "stable_mask.tif"


def validate_inputs() -> None:
    required = [REF_PATH, MASK_PATH, *DEM_PATHS]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing input files:\n" + "\n".join(missing))


def dem_to_nan_array(dem: xdem.DEM) -> np.ndarray:
    """Convert DEM data to float and replace masked/nodata values with NaN."""
    arr = np.squeeze(dem.data)

    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)

    arr = np.asarray(arr, dtype=float)

    if dem.nodata is not None:
        arr[arr == dem.nodata] = np.nan

    arr[arr < -1e20] = np.nan
    arr[arr > 1e20] = np.nan

    return arr


def load_and_align_mask(mask_path: Path, ref_dem: xdem.DEM) -> np.ndarray:
    """
    Load mask and align it to reference DEM grid.
    Assumes stable terrain = 1 and unstable terrain = 0.
    """
    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        aligned_mask = np.zeros(ref_dem.shape, dtype=np.uint8)

        reproject(
            source=mask,
            destination=aligned_mask,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_dem.transform,
            dst_crs=ref_dem.crs,
            resampling=Resampling.nearest,
        )

    stable_mask = aligned_mask.astype(bool)

    logger.info("Stable mask true pixels: %d", int(stable_mask.sum()))
    logger.info("Stable mask false pixels: %d", int((~stable_mask).sum()))

    return stable_mask


def ensure_same_grid(ref_dem: xdem.DEM, dem: xdem.DEM) -> xdem.DEM:
    """Reproject DEM to the reference grid if needed."""
    same_shape = dem.shape == ref_dem.shape
    same_crs = dem.crs == ref_dem.crs
    same_transform = tuple(dem.transform) == tuple(ref_dem.transform)

    if same_shape and same_crs and same_transform:
        return dem

    logger.info("Reprojecting %s to reference grid...", dem.filename)
    return dem.reproject(ref_dem)


def get_stats(ref_dem: xdem.DEM, other_dem: xdem.DEM, stable_mask: np.ndarray) -> dict:
    """Calculate median and NMAD over stable terrain."""
    ref_arr = dem_to_nan_array(ref_dem)
    oth_arr = dem_to_nan_array(other_dem)

    diff = ref_arr - oth_arr
    valid = stable_mask & np.isfinite(ref_arr) & np.isfinite(oth_arr) & np.isfinite(diff)
    vals = diff[valid]

    if vals.size == 0:
        return {"median": np.nan, "nmad": np.nan, "count": 0}

    return {
        "median": float(np.nanmedian(vals)),
        "nmad": float(gu.stats.nmad(vals)),
        "count": int(vals.size),
    }


def extract_coreg_shifts(coreg) -> tuple[float, float, float, float]:
    """Extract dx, dy, dz and horizontal shift magnitude."""
    shift_x = np.nan
    shift_y = np.nan
    shift_z = np.nan

    try:
        matrix = coreg.to_matrix()
        shift_x = float(matrix[0, 3])
        shift_y = float(matrix[1, 3])
        shift_z = float(matrix[2, 3])
    except Exception:
        pass

    horizontal_shift = (
        float(np.sqrt(shift_x**2 + shift_y**2))
        if np.isfinite(shift_x) and np.isfinite(shift_y)
        else np.nan
    )

    return shift_x, shift_y, shift_z, horizontal_shift


def process_dem(ref_dem: xdem.DEM, dem_path: Path, stable_mask: np.ndarray) -> dict:
    logger.info("Processing %s", dem_path.name)

    dem = xdem.DEM(dem_path)
    dem = ensure_same_grid(ref_dem, dem)

    before = get_stats(ref_dem, dem, stable_mask)
    logger.info(
        "Before | NMAD: %.3f | median: %.3f | count: %d",
        before["nmad"], before["median"], before["count"]
    )

    ref_arr = dem_to_nan_array(ref_dem)
    dem_arr = dem_to_nan_array(dem)
    valid_mask = stable_mask & np.isfinite(ref_arr) & np.isfinite(dem_arr)

    logger.info("Valid stable pixels used for fit: %d", int(valid_mask.sum()))

    if valid_mask.sum() == 0:
        raise RuntimeError(f"No valid stable pixels found for {dem_path.name}.")

    coreg = xdem.coreg.NuthKaab()
    coreg.fit(
        reference_elev=ref_dem,
        to_be_aligned_elev=dem,
        inlier_mask=valid_mask
    )

    shift_x, shift_y, shift_z, horizontal_shift = extract_coreg_shifts(coreg)
    logger.info(
        "Estimated shift | dx: %.3f | dy: %.3f | dz: %.3f | horiz: %.3f",
        shift_x, shift_y, shift_z, horizontal_shift
    )

    dem_coreg = coreg.apply(dem)

    out_path = OUTPUT_DIR / f"{dem_path.stem}_coreg.tif"
    dem_coreg.to_file(out_path)
    logger.info("Saved coregistered DEM: %s", out_path)

    after = get_stats(ref_dem, dem_coreg, stable_mask)
    logger.info(
        "After  | NMAD: %.3f | median: %.3f | count: %d",
        after["nmad"], after["median"], after["count"]
    )

    return {
        "DEM": dem_path.name,
        "Shift_X": shift_x,
        "Shift_Y": shift_y,
        "Shift_Z": shift_z,
        "Horizontal_Shift": horizontal_shift,
        "Before_Median": before["median"],
        "Before_NMAD": before["nmad"],
        "Before_Count": before["count"],
        "After_Median": after["median"],
        "After_NMAD": after["nmad"],
        "After_Count": after["count"],
        "Output_Path": str(out_path),
    }


def main() -> None:
    validate_inputs()

    logger.info("Loading reference DEM: %s", REF_PATH)
    ref_dem = xdem.DEM(REF_PATH)

    logger.info("Loading and aligning stable mask: %s", MASK_PATH)
    stable_mask = load_and_align_mask(MASK_PATH, ref_dem)

    results = []
    for dem_path in DEM_PATHS:
        results.append(process_dem(ref_dem, dem_path, stable_mask))

    df = pd.DataFrame(results)

    csv_path = OUTPUT_DIR / "coreg_stats.csv"
    if csv_path.exists():
        try:
            csv_path.unlink()
        except PermissionError:
            raise PermissionError(
                f"{csv_path} is open. Please close it and run again."
            )

    df.to_csv(csv_path, index=False)
    logger.info("Done. Stats saved to %s", csv_path)

    print("\nRESULTS")
    print(df)


if __name__ == "__main__":
    main()