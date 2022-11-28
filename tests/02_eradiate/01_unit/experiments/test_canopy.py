import mitsuba as mi
import numpy as np
import pytest

import eradiate
from eradiate import unit_registry as ureg
from eradiate.contexts import KernelDictContext
from eradiate.exceptions import UnsupportedModeError
from eradiate.experiments import CanopyExperiment
from eradiate.scenes.biosphere import DiscreteCanopy
from eradiate.scenes.measure import MultiDistantMeasure


def test_canopy_experiment_construct_default(modes_all_double):
    """
    CanopyExperiment initialises with default params in all modes
    """
    assert CanopyExperiment()


def test_canopy_experiment_construct_measures(mode_mono_double):
    """
    A variety of measure specifications are acceptable
    """

    # Init with a single measure (not wrapped in a sequence)
    assert CanopyExperiment(measures=MultiDistantMeasure())

    # Init from a dict-based measure spec
    # -- Correctly wrapped in a sequence
    assert CanopyExperiment(measures=[{"type": "distant"}])
    # -- Not wrapped in a sequence
    assert CanopyExperiment(measures={"type": "distant"})


@pytest.mark.parametrize("padding", (0, 1))
def test_canopy_experiment_construct_normalize_measures(mode_mono_double, padding):
    """
    When canopy is not None, measure target matches canopy unit cell
    """
    exp = CanopyExperiment(
        canopy=DiscreteCanopy.homogeneous(
            lai=3.0,
            leaf_radius=0.1 * ureg.m,
            l_horizontal=10.0 * ureg.m,
            l_vertical=2.0 * ureg.m,
            padding=padding,
        ),
        measures=MultiDistantMeasure(),
    )
    target = exp.measures[0].target
    canopy = exp.canopy
    assert np.isclose(target.xmin, -0.5 * canopy.size[0])
    assert np.isclose(target.xmax, 0.5 * canopy.size[0])
    assert np.isclose(target.ymin, -0.5 * canopy.size[1])
    assert np.isclose(target.ymax, 0.5 * canopy.size[1])


@pytest.mark.parametrize("padding", (0, 1))
def test_canopy_experiment_kernel_dict(modes_all_double, padding):
    ctx = KernelDictContext()

    # Surface width is appropriately inherited from canopy
    s = CanopyExperiment(
        canopy=DiscreteCanopy.homogeneous(
            lai=0.5,  # This very low value ensures fast object initialisation
            leaf_radius=0.1 * ureg.m,
            l_horizontal=10.0 * ureg.m,
            l_vertical=2.0 * ureg.m,
            padding=padding,
        )
    )

    kernel_scene = s.kernel_dict(ctx)
    assert np.allclose(
        kernel_scene["shape_surface"]["to_world"].transform_affine(
            mi.Point3f(1, -1, 0)
        ),
        [5 * (2 * padding + 1), -5 * (2 * padding + 1), 0],
    )


@pytest.mark.slow
def test_canopy_experiment_real_life(modes_all_double):
    ctx = KernelDictContext()

    # Construct with typical parameters
    exp = CanopyExperiment(
        surface={"type": "lambertian"},
        canopy={
            "type": "discrete_canopy",
            "construct": "homogeneous",
            "lai": 3.0,
            "leaf_radius": 0.1 * ureg.m,
            "l_horizontal": 10.0 * ureg.m,
            "l_vertical": 2.0 * ureg.m,
        },
        illumination={"type": "directional", "zenith": 45.0},
        measures={
            "type": "distant",
            "construct": "from_viewing_angles",
            "zeniths": np.arange(-60, 61, 5),
            "azimuths": 0.0,
        },
    )
    assert exp.kernel_dict(ctx=ctx).load()


@pytest.mark.slow
def test_canopy_experiment_run_detailed(modes_all_double):
    """
    Test for correctness of the result dataset generated by CanopyExperiment.
    Note: This test is outdated, most of its content should be transferred to
    tests for measure post-processing pipelines.
    """
    if eradiate.mode().is_mono:
        spectral_cfg = {"srf": {"type": "rectangular_srf"}}
        expected_vars = {
            "irradiance",
            "brf",
            "brdf",
            "radiance",
            "spp",
            "srf",
        }
        expected_coords_radiance = {
            "sza",
            "saa",
            "vza",
            "vaa",
            "x_index",
            "x",
            "y_index",
            "y",
            "w",
        }
        expected_coords_irradiance = {"sza", "saa", "w"}

    elif eradiate.mode().is_ckd:
        spectral_cfg = {"bins": ["550"]}
        expected_vars = {
            "irradiance",
            "irradiance_srf",
            "brf",
            "brf_srf",
            "brdf",
            "brdf_srf",
            "radiance",
            "radiance_srf",
            "spp",
            "srf",
        }
        expected_coords_radiance = {
            "bin",
            "bin_wmin",
            "bin_wmax",
            "sza",
            "saa",
            "vza",
            "vaa",
            "x_index",
            "x",
            "y_index",
            "y",
            "w",
        }
        expected_coords_irradiance = {
            "sza",
            "saa",
            "w",
            "bin",
            "bin_wmin",
            "bin_wmax",
        }

    else:
        raise UnsupportedModeError

    exp = CanopyExperiment(
        measures=[
            {
                "type": "hemispherical_distant",
                "id": "toa_hsphere",
                "film_resolution": (32, 32),
                "spp": 1000,
                "spectral_cfg": spectral_cfg,
            },
        ]
    )

    results = eradiate.run(exp)

    # Post-processing creates expected variables ...
    assert set(results.data_vars) == expected_vars

    # ... dimensions
    assert set(results["radiance"].dims) == {"sza", "saa", "x_index", "y_index", "w"}
    assert set(results["irradiance"].dims) == {"sza", "saa", "w"}

    # ... and other coordinates
    assert set(results["radiance"].coords) == expected_coords_radiance
    assert set(results["irradiance"].coords) == expected_coords_irradiance

    # We just check that we record something as expected
    assert np.all(results["radiance"].data > 0.0)
