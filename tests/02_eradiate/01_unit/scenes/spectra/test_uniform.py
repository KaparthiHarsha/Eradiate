import mitsuba as mi
import numpy as np
import pint
import pytest
from pinttr.exceptions import UnitsError

from eradiate import unit_context_config as ucc
from eradiate import unit_context_kernel as uck
from eradiate import unit_registry as ureg
from eradiate.contexts import KernelDictContext
from eradiate.scenes.core import traverse
from eradiate.scenes.spectra import UniformSpectrum, spectrum_factory
from eradiate.units import PhysicalQuantity


@pytest.mark.parametrize(
    "tested, expected",
    [
        (
            {"value": 1.0},
            UniformSpectrum(quantity=PhysicalQuantity.DIMENSIONLESS, value=1.0),
        ),
        (
            {"value": 1},
            UniformSpectrum(quantity=PhysicalQuantity.DIMENSIONLESS, value=1.0),
        ),
        (
            {
                "value": 1.0 * ureg.m**-1,
                "quantity": PhysicalQuantity.COLLISION_COEFFICIENT,
            },
            UniformSpectrum(
                quantity=PhysicalQuantity.COLLISION_COEFFICIENT,
                value=1.0 * ureg.m**-1,
            ),
        ),
        (
            {"value": 1.0, "quantity": "collision_coefficient"},
            UniformSpectrum(
                quantity=PhysicalQuantity.COLLISION_COEFFICIENT,
                value=1.0 * ureg.m**-1,
            ),
        ),
        (
            {"value": 1.0, "quantity": "speed"},
            ValueError,
        ),
        (
            {"quantity": "collision_coefficient", "value": ureg.Quantity(1.0, "")},
            UnitsError,
        ),
    ],
    ids=[
        "float",
        "int",
        "quantity",
        "quantity_convert",
        "unsupported_quantity",
        "inconsistent_units",
    ],
)
def test_uniform_construct(modes_all, tested, expected):
    if isinstance(expected, UniformSpectrum):
        s = UniformSpectrum(**tested)
        assert s.quantity is expected.quantity
        assert np.all(s.value == expected.value)
        assert isinstance(s.value.magnitude, float)

    elif issubclass(expected, Exception):
        with pytest.raises(expected):
            UniformSpectrum(**tested)

    else:
        raise RuntimeError


def test_uniform_kernel_dict(mode_mono):
    # Instantiate from factory using dict
    s = spectrum_factory.convert(
        {
            "type": "uniform",
            "quantity": "radiance",
            "value": 1.0,
            "value_units": "W/km^2/sr/nm",
        }
    )

    # Produced kernel dict is valid
    ctx = KernelDictContext()
    template, _ = traverse(s)
    kernel_dict = template.render(ctx=ctx)
    assert isinstance(mi.load_dict(kernel_dict), mi.Texture)

    # Unit scaling is properly applied
    with ucc.override({"radiance": "W/m^2/sr/nm"}):
        s = UniformSpectrum(quantity="radiance", value=1.0)
    with uck.override({"radiance": "kW/m^2/sr/nm"}):
        ctx = KernelDictContext()
        template, _ = traverse(s)
        kernel_dict = template.render(ctx=ctx)
        assert np.allclose(kernel_dict["value"], 1e-3)


@pytest.mark.parametrize(
    "quantity, value, w, expected",
    [
        ("dimensionless", 1.0, 550.0, 1.0),
        ("dimensionless", 1.0, [500.0, 600.0] * ureg.nm, 1.0),
        ("collision_coefficient", 1.0, 550.0, 1.0 * ureg.m**-1),
        ("collision_coefficient", 1.0, [500.0, 600.0] * ureg.nm, 1.0 * ureg.m**-1),
    ],
)
def test_uniform_eval_mono(mode_mono, quantity, value, w, expected):
    # No quantity, unitless value
    eval = UniformSpectrum(quantity=quantity, value=value).eval_mono(w)
    assert np.all(expected == eval)
    assert isinstance(eval, pint.Quantity)


def test_integral(mode_mono):
    s = UniformSpectrum(value=0.5)
    assert s.integral(300.0, 400.0) == 50.0 * ureg.nm

    s = UniformSpectrum(quantity="collision_coefficient", value=0.5)
    assert s.integral(300.0, 400.0) == 50.0 * ureg("nm / m")
