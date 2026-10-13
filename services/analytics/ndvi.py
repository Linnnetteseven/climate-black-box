"""Landsat Collection 2 Level-2 surface reflectance -> a defensible NDVI mean.

Everything here is a pure function over arrays. No network, no files, no
clock. That is deliberate: these are the numbers we put on stage and claim
are reproducible, so they have to be testable without a satellite.

Two things in this module do the real work, and both are easy to get subtly
wrong:

1. **Scaling.** Collection 2 Level-2 surface reflectance is distributed as
   scaled integers. Reflectance = DN * 0.0000275 - 0.2. Skipping this gives
   an NDVI that looks plausible and is wrong.
2. **Masking.** QA_PIXEL is a bitfield. Cloud, cloud shadow, snow, dilated
   cloud and fill pixels must be dropped *before* the mean, never averaged
   in. A cloudy month that silently averages cloud tops reads as a
   vegetation collapse, and we would raise an alert about the weather.

NDVI is a vegetation greenness indicator. It is not tree survival, canopy
cover, biomass or carbon. Nothing in this file should ever be described as
measuring those.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: USGS Collection 2 Level-2 surface reflectance scaling.
SR_SCALE = 0.0000275
SR_OFFSET = -0.2

#: Valid DN window for L2 surface reflectance. Outside this the retrieval is
#: not trustworthy even when QA_PIXEL does not flag it.
SR_VALID_DN_MIN = 7273
SR_VALID_DN_MAX = 43636

#: QA_PIXEL bit positions, Landsat 8/9 OLI-TIRS Collection 2 Level-2.
QA_FILL = 0
QA_DILATED_CLOUD = 1
QA_CIRRUS = 2
QA_CLOUD = 3
QA_CLOUD_SHADOW = 4
QA_SNOW = 5
QA_CLEAR = 6
QA_WATER = 7

#: Bits that disqualify a pixel from the project mean.
REJECT_BITS = (QA_FILL, QA_DILATED_CLOUD, QA_CIRRUS, QA_CLOUD, QA_CLOUD_SHADOW, QA_SNOW)

PROCESSING_VERSION = "ndvi-v1"


@dataclass(frozen=True)
class NDVISummary:
    """One period's NDVI for one polygon, with the evidence to defend it."""

    mean: float | None
    valid_pixels: int
    total_pixels: int
    #: Share of in-polygon pixels that survived masking. Below ~0.75 the mean
    #: is not trustworthy and the alert engine suppresses on it.
    valid_fraction: float
    processing_version: str = PROCESSING_VERSION

    @property
    def is_usable(self) -> bool:
        return self.mean is not None and self.valid_fraction > 0.0


def bit_is_set(qa: np.ndarray, bit: int) -> np.ndarray:
    """Return a boolean array: is ``bit`` set in each QA_PIXEL value?"""
    return (qa.astype(np.uint16) >> np.uint16(bit)) & np.uint16(1) == 1


def qa_mask(qa: np.ndarray, reject_bits: tuple[int, ...] = REJECT_BITS) -> np.ndarray:
    """Boolean array, True where the pixel is acceptable.

    A pixel is acceptable when none of ``reject_bits`` is set. We do not
    require the CLEAR bit: over vegetation, water-adjacent and hazy-but-usable
    pixels are often not flagged CLEAR yet carry a valid retrieval, and
    demanding CLEAR throws away a third of a scene for no gain.
    """
    rejected = np.zeros(qa.shape, dtype=bool)
    for bit in reject_bits:
        rejected |= bit_is_set(qa, bit)
    return ~rejected


def saturation_mask(*bands: np.ndarray) -> np.ndarray:
    """True where every supplied band sits inside the valid DN window."""
    ok = np.ones(bands[0].shape, dtype=bool)
    for band in bands:
        ok &= (band >= SR_VALID_DN_MIN) & (band <= SR_VALID_DN_MAX)
    return ok


def scale_reflectance(dn: np.ndarray) -> np.ndarray:
    """Convert scaled integer DN to surface reflectance."""
    return dn.astype(np.float64) * SR_SCALE + SR_OFFSET


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red), with a zero denominator -> NaN.

    Inputs are reflectance, not DN. Scale first.
    """
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    denominator = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denominator == 0, np.nan, (nir - red) / denominator)
    return out


def summarise(
    nir_dn: np.ndarray,
    red_dn: np.ndarray,
    qa: np.ndarray,
    polygon_mask: np.ndarray | None = None,
) -> NDVISummary:
    """Compute the project-area NDVI mean for one period.

    ``polygon_mask`` is True inside the project boundary. When omitted the
    whole array is treated as inside, which is what the unit tests do.

    The returned ``valid_fraction`` is relative to the pixels *inside the
    polygon*, not the whole scene -- a scene that is 60% cloud but clear over
    our 200 hectares is a good observation, and the number we report should
    say so.
    """
    nir_dn = np.asarray(nir_dn)
    red_dn = np.asarray(red_dn)
    qa = np.asarray(qa)

    inside = np.ones(nir_dn.shape, dtype=bool) if polygon_mask is None else np.asarray(polygon_mask, dtype=bool)
    total = int(inside.sum())
    if total == 0:
        return NDVISummary(mean=None, valid_pixels=0, total_pixels=0, valid_fraction=0.0)

    usable = inside & qa_mask(qa) & saturation_mask(nir_dn, red_dn)

    values = ndvi(scale_reflectance(nir_dn), scale_reflectance(red_dn))
    usable &= np.isfinite(values)

    valid = int(usable.sum())
    if valid == 0:
        return NDVISummary(mean=None, valid_pixels=0, total_pixels=total, valid_fraction=0.0)

    # Only the surviving pixels reach the mean. This line is the whole point
    # of the module.
    mean = float(values[usable].mean())
    return NDVISummary(
        mean=mean,
        valid_pixels=valid,
        total_pixels=total,
        valid_fraction=valid / total,
    )
