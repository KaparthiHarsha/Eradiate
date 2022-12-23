import typing as t

import attrs

from ._core import BSDFNode
from ..core import NodeSceneElement
from ..spectra import SpectrumNode, spectrum_factory
from ... import validators
from ...attrs import documented, parse_docs


@parse_docs
@attrs.define(eq=False, slots=False)
class LambertianBSDF(BSDFNode):
    """
    Lambertian BSDF [``lambertian``].

    This class implements the Lambertian (a.k.a. diffuse) reflectance model.
    A surface with this scattering model attached scatters radiation equally in
    every direction.
    """

    reflectance: SpectrumNode = documented(
        attrs.field(
            default=0.5,
            converter=spectrum_factory.converter("reflectance"),
            validator=[
                attrs.validators.instance_of(SpectrumNode),
                validators.has_quantity("reflectance"),
            ],
        ),
        doc="Reflectance spectrum. Can be initialised with a dictionary "
        "processed by :data:`.spectrum_factory`.",
        type=".SpectrumNode",
        init_type=".SpectrumNode or dict or float",
        default="0.5",
    )

    @property
    def template(self) -> dict:
        return {"type": "diffuse"}

    @property
    def objects(self) -> t.Dict[str, NodeSceneElement]:
        return {"reflectance": self.reflectance}
