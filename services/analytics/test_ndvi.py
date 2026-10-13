"""Unit tests for the NDVI/QA core, on hand-built arrays.

These are the numbers we defend on stage, so they are tested without a
satellite: every array here is small enough to reason about by hand.
"""

import numpy as np
import pytest

from services.analytics.ndvi import (
    QA_CLOUD,
    QA_CLOUD_SHADOW,
    QA_DILATED_CLOUD,
    QA_FILL,
    QA_SNOW,
    QA_WATER,
    SR_OFFSET,
    SR_SCALE,
    SR_VALID_DN_MAX,
    SR_VALID_DN_MIN,
    bit_is_set,
    ndvi,
    qa_mask,
    saturation_mask,
    scale_reflectance,
    summarise,
)

CLEAR = 0
# A healthy-vegetation pair: NIR high, red low, both inside the valid window.
VEG_NIR, VEG_RED = 30000, 9000
# A bare/stressed pair: the two bands much closer together.
BARE_NIR, BARE_RED = 14000, 11000


def _bits(*positions: int) -> int:
    value = 0
    for p in positions:
        value |= 1 << p
    return value


# --- bit unpacking ---------------------------------------------------------

def test_bit_is_set_reads_each_position():
    qa = np.array([_bits(QA_CLOUD), _bits(QA_SNOW), CLEAR], dtype=np.uint16)
    assert bit_is_set(qa, QA_CLOUD).tolist() == [True, False, False]
    assert bit_is_set(qa, QA_SNOW).tolist() == [False, True, False]


def test_bit_is_set_handles_several_bits_at_once():
    qa = np.array([_bits(QA_CLOUD, QA_CLOUD_SHADOW)], dtype=np.uint16)
    assert bit_is_set(qa, QA_CLOUD)[0]
    assert bit_is_set(qa, QA_CLOUD_SHADOW)[0]
    assert not bit_is_set(qa, QA_SNOW)[0]


@pytest.mark.parametrize("bit", [QA_FILL, QA_DILATED_CLOUD, QA_CLOUD, QA_CLOUD_SHADOW, QA_SNOW])
def test_every_reject_bit_excludes_the_pixel(bit):
    qa = np.array([CLEAR, _bits(bit)], dtype=np.uint16)
    assert qa_mask(qa).tolist() == [True, False]


def test_water_alone_does_not_exclude_a_pixel():
    """Water is information, not a defect. We record it; we do not drop it."""
    qa = np.array([_bits(QA_WATER)], dtype=np.uint16)
    assert qa_mask(qa).tolist() == [True]


def test_clear_bit_is_not_required():
    qa = np.array([CLEAR], dtype=np.uint16)
    assert qa_mask(qa).tolist() == [True]


# --- scaling ---------------------------------------------------------------

def test_scale_reflectance_applies_offset_and_scale():
    dn = np.array([10000], dtype=np.uint16)
    assert scale_reflectance(dn)[0] == pytest.approx(10000 * SR_SCALE + SR_OFFSET)


def test_unscaled_dn_would_give_a_wrong_ndvi():
    """Guards the single easiest mistake in the pipeline."""
    scaled = ndvi(scale_reflectance(np.array([VEG_NIR])), scale_reflectance(np.array([VEG_RED])))
    raw = ndvi(np.array([VEG_NIR], dtype=float), np.array([VEG_RED], dtype=float))
    assert not np.isclose(scaled[0], raw[0])


# --- saturation ------------------------------------------------------------

def test_saturation_mask_rejects_values_outside_the_valid_window():
    nir = np.array([SR_VALID_DN_MIN - 1, VEG_NIR, SR_VALID_DN_MAX + 1], dtype=np.int32)
    red = np.array([VEG_RED, VEG_RED, VEG_RED], dtype=np.int32)
    assert saturation_mask(nir, red).tolist() == [False, True, False]


# --- ndvi ------------------------------------------------------------------

def test_ndvi_of_vegetation_is_higher_than_bare_ground():
    veg = ndvi(scale_reflectance(np.array([VEG_NIR])), scale_reflectance(np.array([VEG_RED])))
    bare = ndvi(scale_reflectance(np.array([BARE_NIR])), scale_reflectance(np.array([BARE_RED])))
    assert veg[0] > bare[0]


def test_ndvi_stays_within_minus_one_and_one():
    rng = np.random.default_rng(0)
    nir = rng.integers(SR_VALID_DN_MIN, SR_VALID_DN_MAX, 500)
    red = rng.integers(SR_VALID_DN_MIN, SR_VALID_DN_MAX, 500)
    values = ndvi(scale_reflectance(nir), scale_reflectance(red))
    finite = values[np.isfinite(values)]
    assert finite.min() >= -1.0 and finite.max() <= 1.0


def test_zero_denominator_is_nan_not_a_crash():
    out = ndvi(np.array([0.0]), np.array([0.0]))
    assert np.isnan(out[0])


# --- the summary, which is what the rest of the system consumes ------------

def test_invalid_pixels_are_never_averaged_in():
    """The property the whole alert story depends on."""
    nir = np.array([VEG_NIR, VEG_NIR, BARE_NIR], dtype=np.int32)
    red = np.array([VEG_RED, VEG_RED, BARE_RED], dtype=np.int32)
    qa = np.array([CLEAR, CLEAR, _bits(QA_CLOUD)], dtype=np.uint16)

    masked = summarise(nir, red, qa)
    unmasked = summarise(nir, red, np.array([CLEAR, CLEAR, CLEAR], dtype=np.uint16))

    assert masked.valid_pixels == 2
    assert masked.mean > unmasked.mean  # the cloudy low-NDVI pixel dragged it down
    expected = ndvi(scale_reflectance(np.array([VEG_NIR])), scale_reflectance(np.array([VEG_RED])))[0]
    assert masked.mean == pytest.approx(expected)


def test_valid_fraction_is_relative_to_the_polygon_not_the_scene():
    nir = np.full(10, VEG_NIR, dtype=np.int32)
    red = np.full(10, VEG_RED, dtype=np.int32)
    qa = np.zeros(10, dtype=np.uint16)
    qa[5:] = _bits(QA_CLOUD)  # half the scene is cloudy...
    inside = np.zeros(10, dtype=bool)
    inside[:4] = True  # ...but our polygon sits in the clear half

    summary = summarise(nir, red, qa, polygon_mask=inside)
    assert summary.total_pixels == 4
    assert summary.valid_pixels == 4
    assert summary.valid_fraction == 1.0


def test_fully_clouded_period_returns_no_mean_rather_than_a_guess():
    nir = np.full(4, VEG_NIR, dtype=np.int32)
    red = np.full(4, VEG_RED, dtype=np.int32)
    qa = np.full(4, _bits(QA_CLOUD), dtype=np.uint16)

    summary = summarise(nir, red, qa)
    assert summary.mean is None
    assert summary.valid_fraction == 0.0
    assert not summary.is_usable


def test_partial_coverage_reports_an_honest_fraction():
    nir = np.full(8, VEG_NIR, dtype=np.int32)
    red = np.full(8, VEG_RED, dtype=np.int32)
    qa = np.zeros(8, dtype=np.uint16)
    qa[:6] = _bits(QA_CLOUD_SHADOW)

    summary = summarise(nir, red, qa)
    assert summary.valid_pixels == 2
    assert summary.total_pixels == 8
    assert summary.valid_fraction == pytest.approx(0.25)


def test_empty_polygon_is_handled():
    nir = np.full(4, VEG_NIR, dtype=np.int32)
    red = np.full(4, VEG_RED, dtype=np.int32)
    qa = np.zeros(4, dtype=np.uint16)
    summary = summarise(nir, red, qa, polygon_mask=np.zeros(4, dtype=bool))
    assert summary.mean is None and summary.total_pixels == 0
