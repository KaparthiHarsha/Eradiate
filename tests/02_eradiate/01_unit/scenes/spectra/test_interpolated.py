import mitsuba as mi
import numpy as np
import pint
import pinttr
import pytest

import eradiate
from eradiate import unit_context_config as ucc
from eradiate import unit_context_kernel as uck
from eradiate import unit_registry as ureg
from eradiate.ckd import BinSet
from eradiate.contexts import KernelDictContext
from eradiate.scenes.spectra import InterpolatedSpectrum, spectrum_factory
from eradiate.spectral_index import SpectralIndex
from eradiate.units import PhysicalQuantity


def test_interpolated_construct(modes_all):
    # Instantiating without argument fails
    with pytest.raises(TypeError):
        InterpolatedSpectrum()
    # Instantiating with missing argument fails
    with pytest.raises(TypeError):
        InterpolatedSpectrum(wavelengths=[500.0, 600.0])
    with pytest.raises(TypeError):
        InterpolatedSpectrum(values=[0.0, 1.0])
    # Shape mismatch raises
    with pytest.raises(ValueError):
        InterpolatedSpectrum(wavelengths=[500.0, 600.0], values=[0.0, 1.0, 2.0])

    # Instantiating with no quantity makes spectrum dimensionless
    spectrum = InterpolatedSpectrum(wavelengths=[500.0, 600.0], values=[0.0, 1.0])
    assert spectrum.quantity is PhysicalQuantity.DIMENSIONLESS
    assert isinstance(spectrum.values, pint.Quantity)
    # Instantiating with a quantity applies units
    spectrum = InterpolatedSpectrum(
        quantity="irradiance", wavelengths=[500.0, 600.0], values=[0.0, 1.0]
    )
    assert spectrum.values.is_compatible_with("W/m^2/nm")

    # Inconsistent units raise
    with pytest.raises(pinttr.exceptions.UnitsError):
        InterpolatedSpectrum(
            quantity="irradiance",
            wavelengths=[500.0, 600.0],
            values=[0.0, 1.0] * ureg("W/m^2"),
        )
    with pytest.raises(pinttr.exceptions.UnitsError):
        InterpolatedSpectrum(
            quantity="irradiance",
            wavelengths=[500.0, 600.0] * ureg.s,
            values=[0.0, 1.0],
        )

    # Instantiate from factory
    assert spectrum_factory.convert(
        {
            "type": "interpolated",
            "quantity": "irradiance",
            "wavelengths": [0.5, 0.6],
            "wavelengths_units": "micron",
            "values": [0.5, 1.0],
            "values_units": "kW/m^2/nm",
        }
    )


@pytest.mark.parametrize(
    "quantity, values, w, expected",
    [
        (
            "dimensionless",
            [0.0, 1.0],
            [450.0, 500.0, 550.0, 600.0, 650.0] * ureg.nm,
            [0.0, 0.0, 0.5, 1.0, 0.0],
        ),
        (
            "collision_coefficient",
            [0.0, 1.0],
            [450.0, 500.0, 550.0, 600.0, 650.0] * ureg.nm,
            [0.0, 0.0, 0.5, 1.0, 0.0] * ureg.m**-1,
        ),
    ],
)
def test_interpolated_eval_mono(mode_mono, quantity, values, w, expected):
    # No quantity, unitless value
    eval = InterpolatedSpectrum(
        quantity=quantity, values=values, wavelengths=[500.0, 600.0]
    ).eval_mono(w)
    assert np.all(expected == eval)
    assert isinstance(eval, pint.Quantity)


def test_interpolated_eval_mono_wavelengths_decreasing(mode_mono):
    # decreasing wavelength values
    with pytest.raises(ValueError):
        InterpolatedSpectrum(
            quantity="dimensionless",
            values=[0.0, 1.0],
            wavelengths=[600.0, 500.0],
        )


def test_interpolated_eval(modes_all):
    if eradiate.mode().is_mono:
        spectral_index = SpectralIndex.new(w=550.0)
        expected = 0.5

    elif eradiate.mode().is_ckd:
        bin = BinSet.from_db("10nm").select_bins("550")[0]
        spectral_index = SpectralIndex.new(w=bin.wcenter)
        expected = 0.5

    else:
        assert False

    # Spectrum performs linear interpolation and yields units consistent with
    # quantity
    spectrum = InterpolatedSpectrum(wavelengths=[500.0, 600.0], values=[0.0, 1.0])
    assert spectrum.eval(spectral_index) == expected * ureg.dimensionless

    spectrum = InterpolatedSpectrum(
        quantity="irradiance", wavelengths=[500.0, 600.0], values=[0.0, 1.0]
    )
    # Interpolation returns quantity
    assert spectrum.eval(spectral_index) == expected * ucc.get("irradiance")


def test_interpolated_kernel_dict(modes_all_mono):
    ctx = KernelDictContext(spectral_index=SpectralIndex.new(w=550.0))

    spectrum = InterpolatedSpectrum(
        id="spectrum",
        quantity="irradiance",
        wavelengths=[500.0, 600.0],
        values=[0.0, 1.0],
    )

    # Produced kernel dict is valid
    assert isinstance(spectrum.kernel_dict(ctx=ctx).load(), mi.Texture)

    # Unit scaling is properly applied
    with ucc.override({"radiance": "W/m^2/sr/nm"}):
        s = InterpolatedSpectrum(
            quantity="radiance", wavelengths=[500.0, 600.0], values=[0.0, 1.0]
        )
    with uck.override({"radiance": "kW/m^2/sr/nm"}):
        d = s.kernel_dict(ctx)
        assert np.allclose(d["spectrum"]["value"], 5e-4)


def test_interpolated_from_dataarray(mode_mono):
    da = eradiate.data.load_dataset(
        "spectra/reflectance/lambertian_soil_01.nc"
    ).reflectance
    spectrum = InterpolatedSpectrum.from_dataarray(dataarray=da)
    assert np.all(spectrum.wavelengths.m_as(da.w.attrs["units"]) == da.w.values)
    assert np.all(spectrum.values.m_as(da.attrs["units"]) == da.values)
