import typing as t

import attrs
import mitsuba as mi

from ._core import BSDFNode
from ..core import NodeSceneElement, traverse
from ..spectra import SpectrumNode, spectrum_factory
from ... import validators
from ...attrs import documented, parse_docs
from ...kernel import InitParameter, TypeIdLookupStrategy, UpdateParameter


@parse_docs
@attrs.define(eq=False, slots=False)
class RPVBSDF(BSDFNode):
    """
    RPV BSDF [``rpv``].

    This BSDF implements the Rahman-Pinty-Verstraete (RPV) reflection model
    :cite:`Rahman1993CoupledSurfaceatmosphereReflectance,Pinty2000SurfaceAlbedoRetrieval`.
    It notably features a controllable back-scattering lobe (`hot spot`)
    characteristic of many natural land surfaces and is frequently used in Earth
    observation because of its simple parametrisation.

    See Also
    --------
    :ref:`plugin-bsdf-rpv`

    Notes
    -----
    * The default configuration is typical of grassland in the visible domain
      (:cite:`Rahman1993CoupledSurfaceatmosphereReflectance`, Table 1).
    * Parameter names are defined as per the symbols used in the Eradiate
      Scientific Handbook :cite:`EradiateScientificHandbook2020`.
    """

    rho_0: SpectrumNode = documented(
        attrs.field(
            default=0.183,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(SpectrumNode),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Amplitude parameter. Must be dimensionless. "
        "Should be in :math:`[0, 1]`.",
        type=".SpectrumNode",
        init_type=".SpectrumNode or dict or float, optional",
        default="0.183",
    )

    rho_c: t.Optional[SpectrumNode] = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(
                spectrum_factory.converter("dimensionless")
            ),
            validator=attrs.validators.optional(
                [
                    attrs.validators.instance_of(SpectrumNode),
                    validators.has_quantity("dimensionless"),
                ]
            ),
        ),
        doc="Hot spot parameter. Must be dimensionless. "
        r"Should be in :math:`[0, 1]`. If unset, :math:`\rho_\mathrm{c}` "
        r"defaults to the kernel plugin default (equal to :math:`\rho_0`).",
        type=".SpectrumNode or None",
        init_type=".SpectrumNode or dict or float or None, optional",
        default="None",
    )

    k: SpectrumNode = documented(
        attrs.field(
            default=0.780,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(SpectrumNode),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Bowl-shape parameter. Must be dimensionless. "
        "Should be in :math:`[0, 2]`.",
        type=".SpectrumNode",
        init_type=".SpectrumNode or dict or float, optional",
        default="0.780",
    )

    g: SpectrumNode = documented(
        attrs.field(
            default=-0.1,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(SpectrumNode),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Asymmetry parameter. Must be dimensionless. "
        "Should be in :math:`[-1, 1]`.",
        type=".SpectrumNode",
        init_type=".SpectrumNode or dict or float, optional",
        default="-0.1",
    )

    @property
    def template(self) -> dict:
        objects = {
            "rho_0": traverse(self.rho_0)[0],
            "k": traverse(self.k)[0],
            "g": traverse(self.g)[0],
        }

        if self.rho_c is not None:
            objects["rho_c"] = traverse(self.rho_c)[0]

        result = {"type": "rpv"}

        for obj_key, obj_values in objects.items():
            for key, value in obj_values.items():
                result[f"{obj_key}.{key}"] = value

        return result

    @property
    def params(self) -> t.Dict[str, UpdateParameter]:
        objects = {
            "rho_0": traverse(self.rho_0)[1],
            "k": traverse(self.k)[1],
            "g": traverse(self.g)[1],
        }

        if self.rho_c is not None:
            objects["rho_c"] = traverse(self.rho_c)[1]

        result = {}
        for obj_key, obj_params in objects.items():
            for key, param in obj_params.items():
                result[f"{obj_key}.{key}"] = attrs.evolve(
                    param,
                    lookup_strategy=TypeIdLookupStrategy(
                        node_type=mi.BSDF,
                        node_id=self.id,
                        parameter_relpath=f"{obj_key}.{key}",
                    ),
                )

        return result
