import typing as t

import attrs

from ._core import PhaseFunction
from ..spectra import SpectrumNode, spectrum_factory
from ... import validators
from ...attrs import documented, parse_docs
from ...kernel import InitParameter, UpdateParameter


@parse_docs
@attrs.define(eq=False, slots=False)
class HenyeyGreensteinPhaseFunction(PhaseFunction):
    """
    Henyey-Greenstein phase function [``hg``].

    The Henyey-Greenstein phase function :cite:`Henyey1941Diffuse` models
    scattering in an isotropic medium. The scattering pattern is controlled by
    its :math:`g` parameter, which is equal to the phase function's asymmetry
    parameter (the mean cosine of the scattering angle): a positive (resp.
    negative) value corresponds to predominant forward (resp. backward)
    scattering.
    """

    g: SpectrumNode = documented(
        attrs.field(
            default=0.0,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(SpectrumNode),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Asymmetry parameter. Must be dimensionless. "
        "Must be in :math:`]-1, 1[`.",
        type=":class:`.Spectrum`",
        init_type=":class:`.Spectrum` or dict or float, optional",
        default="0.0",
    )

    @property
    def template(self) -> dict:
        return {
            "type": "hg",
            "g": InitParameter(lambda ctx: float(self.g.eval(ctx.spectral_ctx))),
        }

    @property
    def params(self) -> t.Dict[str, UpdateParameter]:
        return {
            "g": UpdateParameter(
                lambda ctx: float(self.g.eval(ctx.spectral_ctx)),
                UpdateParameter.Flags.SPECTRAL,
            )
        }
