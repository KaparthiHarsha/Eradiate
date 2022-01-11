import numpy as np
import pytest

from eradiate.kernel.gridvolume import write_binary_grid3d


def gridvol_constant(basepath, data=[[[1.0]]]):
    filename = basepath / "gridvol_const.vol"
    data = np.array(data)
    write_binary_grid3d(filename, data)
    return filename


def test_construct(variant_scalar_rgb, tmp_path):
    from mitsuba.core import ScalarTransform4f, load_dict

    # Construct without parameters
    volume = load_dict({"type": "grid_spherical"})
    assert volume is not None

    # Construct with rmin > rmax:
    with pytest.raises(Exception):
        load_dict({"type": "grid_spherical", "rmin": 0.8, "rmax": 0.2})

    # Construct with all parameters set to typical values
    gridvol_filename = gridvol_constant(tmp_path)
    volume = load_dict(
        {
            "type": "grid_spherical",
            "rmin": 0.0,
            "rmax": 1.0,
            "fillmin": 0.0,
            "fillmax": 0.0,
            "gridvolume": {
                "type": "gridvolume",
                "filename": str(gridvol_filename)
            }
        }
    )
    assert volume is not None


def test_eval_basic(variant_scalar_rgb, tmp_path):
    from mitsuba.core import load_dict
    from mitsuba.render import Interaction3f
    gridvol_filename = gridvol_constant(tmp_path, data=[[[2.0]]])
    volume = load_dict(
        {
            "type": "grid_spherical",
            "rmin": 0.2,
            "rmax": 0.8,
            "fillmin": 3.0,
            "fillmax": 1.0,
            "gridvolume": {
                "type": "gridvolume",
                "filename": str(gridvol_filename)
            }
        }
    )

    p_outside_max = [0.9, 0.0, 0.0]
    p_outside_min = [0.0, 0.0, 0.1]
    p_inside = [0.0, 0.5, 0.0]

    it_outside_max = Interaction3f()
    it_outside_max.p = p_outside_max
    it_outside_min = Interaction3f()
    it_outside_min.p = p_outside_min
    it_inside = Interaction3f()
    it_inside.p = p_inside

    assert volume.eval(it_outside_max) == 1.0
    assert volume.eval(it_outside_min) == 3.0
    assert volume.eval(it_inside) == 2.0


def test_eval_advanced(variant_scalar_mono, tmp_path):
    from mitsuba.core import load_dict
    from mitsuba.render import Interaction3f
    data = np.arange(1, 7, 1)
    sigma_t = np.zeros((6, 2, 2))
    sigma_t[:, 0, 0] = data
    sigma_t[:, 0, 1] = data
    sigma_t[:, 1, 0] = data
    sigma_t[:, 1, 1] = data
    gridvol_filename = gridvol_constant(tmp_path, data=sigma_t)
    volume = load_dict(
        {
            "type": "grid_spherical",
            "rmin": 0.0,
            "rmax": 1.0,
            "fillmin": 3.0,
            "fillmax": 1.0,
            "gridvolume": {
                "type": "gridvolume",
                "filename": str(gridvol_filename),
                "filter_type": "nearest"
            }
        }
    )

    # have one point in each sector of the spherical volume
    angles = [5, 65, 125, 185, 245, 305]
    results = []
    for angle in angles:
        p = [0.5*np.cos(np.deg2rad(angle)), 0.5*np.sin(np.deg2rad(angle)), 0.0]
        print(f"Angle: {angle}, Point: {p}")
        it = Interaction3f()
        it.p = p
        results.append(volume.eval(it))

    # This order looks strange, but the output of enokis atan2 function
    # does not map the [0: 2pi] range to [0:1] but is shifted by pi
    assert np.all(np.squeeze(results) == [4.0, 5.0, 6.0, 1.0, 2.0, 3.0])
