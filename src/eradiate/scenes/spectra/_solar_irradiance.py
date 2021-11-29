from __future__ import annotations

import datetime
import typing as t

import astropy.coordinates
import astropy.time
import astropy.units
import attr
import dateutil
import numpy as np
import pint
import xarray as xr

from ._core import Spectrum, spectrum_factory
from ..core import KernelDict
from ... import data, validators
from ...attrs import documented, parse_docs
from ...ckd import Bindex
from ...contexts import KernelDictContext, SpectralContext
from ...units import PhysicalQuantity, to_quantity
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg


@spectrum_factory.register(type_id="solar_irradiance")
@parse_docs
@attr.s(frozen=True)
class SolarIrradianceSpectrum(Spectrum):
    """
    Solar irradiance spectrum scene element [``solar_irradiance``].

    This scene element produces the scene dictionary required to
    instantiate a kernel plugin using the Sun irradiance spectrum. The data set
    used by this element is controlled by the ``dataset`` field (see
    :mod:`eradiate.data.solar_irradiance_spectra` for available data sets).

    Notes
    ------

    * The spectral range of the data sets shipped can vary and an attempt for
      use outside of the supported spectral range will raise a
      :class:`ValueError` upon calling :meth:`kernel_dict`.

    * The spectrum is automatically adjusted when the ``datetime`` field is set.
      Datasets without a time dimension are assumed to be normalised to a given
      Earth-Sun distance and the data is scaled based on the actual Earth-Sun
      distance for the specified date, computed using the ephemeris of
      :func:`astropy.coordinates.get_sun`.

    * The ``scale`` field can be used to apply additional arbitrary scaling.
      It is mostly used for debugging purposes.

    * The evaluation method depends on the active mode:

      * in ``mono_*`` modes, the spectrum is evaluated at the spectral context
        wavelength;
      * in ``ckd_*`` modes, the spectrum is evaluated as the average value over
        the spectral context bin (the integral is computed using a trapezoid
        rule).

    * The produced kernel dictionary automatically adjusts its irradiance units
      depending on the selected kernel default units.
    """

    # --------------------------------------------------------------------------
    #                           Fields and properties
    # --------------------------------------------------------------------------

    quantity: PhysicalQuantity = attr.ib(
        default=PhysicalQuantity.IRRADIANCE, init=False, repr=False
    )

    dataset: str = documented(
        attr.ib(
            default="thuillier_2003",
            validator=attr.validators.instance_of(str),
        ),
        doc="Dataset identifier. Allowed values: see "
        ":attr:`solar irradiance dataset documentation <eradiate.data.solar_irradiance_spectra>`.",
        type="str",
        default='``"thuiller_2003"``',
    )

    @dataset.validator
    def _dataset_validator(self, attribute, value):
        if value not in data.registered("solar_irradiance_spectrum"):
            raise ValueError(
                f"while setting {attribute.name}: '{value}' not in "
                f"list of supported solar irradiance spectra "
                f"{data.registered('solar_irradiance_spectrum')}"
            )

    scale: float = documented(
        attr.ib(default=1.0, converter=float, validator=validators.is_positive),
        doc="Arbitrary scaling factor.",
        type="float or datetime",
        init_type="float or datetime or str",
        default="1.0",
    )

    datetime: t.Optional[datetime.datetime] = documented(
        attr.ib(
            default=None,
            converter=attr.converters.optional(dateutil.parser.parse),
        ),
        type="datetime or None",
        init_type="datetime or str, optional",
        doc="Date for which the spectrum is to be evaluated. An ISO "
        "string can be passed and will be interpreted by "
        ":meth:`dateutil.parser.parse`.",
    )

    data: xr.Dataset = attr.ib(init=False, repr=False)

    @data.default
    def _data_factory(self):
        # Load dataset
        try:
            with data.open("solar_irradiance_spectrum", self.dataset) as ds:
                result = ds
            return result
        except KeyError as e:
            raise ValueError(f"unknown dataset {self.dataset}") from e

    def _scale_earth_sun_distance(self) -> float:
        """
        Compute scaling factor applied to the irradiance spectrum based on the
        Earth-Sun distance.
        """
        # Note: We assume that the loaded dataset is for a reference
        # Earth-Sun distance of 1 AU
        if self.datetime is None:
            return 1.0

        else:
            return (
                float(
                    astropy.coordinates.get_sun(
                        astropy.time.Time(self.datetime)
                    ).distance
                    / astropy.units.au
                )
                ** 2
            )

    def eval(self, spectral_ctx: SpectralContext) -> pint.Quantity:
        if self.dataset == "solid_2017":
            raise NotImplementedError(
                "Solar irradiance spectrum datasets with a non-empty time "
                "coordinate are not supported yet."
            )
        # TODO: add support to solar irradiance spectrum datasets with a
        #  non-empty time coordinate

        return super(SolarIrradianceSpectrum, self).eval(spectral_ctx)

    def eval_mono(self, w: pint.Quantity) -> pint.Quantity:
        w_units = ureg(self.data.ssi.w.attrs["units"])
        irradiance = to_quantity(
            self.data.ssi.interp(w=w.m_as(w_units), method="linear")
        )

        # Raise if out of bounds or ill-formed dataset
        if np.any(np.isnan(irradiance.magnitude)):
            raise ValueError("dataset interpolation returned nan")

        return irradiance * self.scale * self._scale_earth_sun_distance()

    def eval_ckd(self, *bindexes: Bindex) -> pint.Quantity:
        # Spectrum is averaged over spectral bin

        result = np.zeros((len(bindexes),))
        wavelength_units = ucc.get("wavelength")
        quantity_units = ucc.get(self.quantity)

        for i_bindex, bindex in enumerate(bindexes):
            bin = bindex.bin

            wmin_m = bin.wmin.m_as(wavelength_units)
            wmax_m = bin.wmax.m_as(wavelength_units)

            # -- Collect relevant spectral coordinate values
            w_m = ureg.convert(
                self.data.ssi.w.values, self.data.ssi.w.attrs["units"], wavelength_units
            )
            w = (
                np.hstack(
                    (
                        [wmin_m],
                        w_m[np.where(np.logical_and(wmin_m < w_m, w_m < wmax_m))[0]],
                        [wmax_m],
                    )
                )
                * wavelength_units
            )

            # -- Evaluate spectrum at wavelengths
            interp = self.eval_mono(w)

            # -- Average spectrum on bin extent
            integral = np.trapz(interp, w)
            result[i_bindex] = (integral / bin.width).m_as(quantity_units)

        return result * quantity_units

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        # Apply scaling, build kernel dict
        value = float(self.eval(ctx.spectral_ctx).m_as(uck.get("irradiance")))
        return KernelDict(
            {
                "spectrum": {
                    "type": "uniform",
                    "value": value,
                }
            }
        )

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        raise NotImplementedError
