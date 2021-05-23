import warnings
from abc import ABC, abstractmethod
from typing import Dict, Optional, Union

import attr
import pint
import pinttr

from ..core import SceneElement
from ... import converters, validators
from ..._attrs import documented, get_doc, parse_docs
from ..._factory import BaseFactory
from ...contexts import KernelDictContext
from ...exceptions import ConfigWarning, OverriddenValueWarning
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg


@parse_docs
@attr.s
class Surface(SceneElement, ABC):
    """
    An abstract base class defining common facilities for all surfaces.
    All these surfaces consist of a square parametrised by its width.
    """

    id: Optional[str] = documented(
        attr.ib(
            default="surface",
            validator=attr.validators.optional(attr.validators.instance_of(str)),
        ),
        doc=get_doc(SceneElement, "id", "doc"),
        type=get_doc(SceneElement, "id", "type"),
        default='"surface"',
    )

    width: Union[pint.Quantity, str] = documented(
        pinttr.ib(
            default="auto",
            converter=converters.auto_or(
                pinttr.converters.to_units(ucc.deferred("length"))
            ),
            validator=[
                validators.auto_or(validators.is_positive),
                validators.auto_or(pinttr.validators.has_compatible_units),
            ],
            units=ucc.deferred("length"),
        ),
        doc="Surface size. Without contextual constraint (*e.g.* if the surface "
        'has no canopy or atmosphere above it), "auto" defaults to 100 km.\n'
        "\n"
        "Unit-enabled field (default: cdu[length]).",
        type='float or "auto"',
        default='"auto"',
    )

    @abstractmethod
    def bsdfs(self, ctx: KernelDictContext = None):
        """
        Return BSDF plugin specifications only.

        Parameter ``ctx`` (:class:`.KernelDictContext` or None):
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns → dict:
            Return a dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the BSDFs
            attached to the surface.
        """
        pass

    def shapes(self, ctx: KernelDictContext = None):
        """
        Return shape plugin specifications only.

        Parameter ``ctx`` (:class:`.KernelDictContext` or None):
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns → dict:
            A dictionary suitable for merge with a
            :class:`~eradiate.scenes.core.KernelDict` containing all the shapes
            attached to the surface.
        """
        from mitsuba.core import ScalarTransform4f, ScalarVector3f

        if ctx.ref:
            bsdf = {"type": "ref", "id": f"bsdf_{self.id}"}
        else:
            bsdf = self.bsdfs()[f"bsdf_{self.id}"]

        width = self.kernel_width(ctx=ctx).m_as(uck.get("length"))

        return {
            f"shape_{self.id}": {
                "type": "rectangle",
                "to_world": ScalarTransform4f.scale(
                    ScalarVector3f(width * 0.5, width * 0.5, 1.0)
                ),
                "bsdf": bsdf,
            }
        }

    def kernel_width(self, ctx: KernelDictContext = None):
        """
        Return width of kernel object, possibly overridden by
        ``ctx.override_surface_width``.

        Parameter ``ctx`` (:class:`.KernelDictContext` or None):
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns → :class:`pint.Quantity`:
            Kernel object width.
        """
        if ctx is not None and ctx.override_surface_width is not None:
            if self.width != "auto":
                warnings.warn(OverriddenValueWarning("Overriding surface width"))
            return ctx.override_surface_width
        else:
            if self.width != "auto":
                return self.width
            else:
                return 100.0 * ureg.km

    def kernel_dict(self, ctx: KernelDictContext = None) -> Dict:
        kernel_dict = {}

        if not ctx.ref:
            kernel_dict[self.id] = self.shapes(ctx)[f"shape_{self.id}"]
        else:
            kernel_dict[f"bsdf_{self.id}"] = self.bsdfs(ctx)[f"bsdf_{self.id}"]
            kernel_dict[self.id] = self.shapes(ctx)[f"shape_{self.id}"]

        return kernel_dict

    def scaled(self, factor: float) -> "Surface":
        """
        Return a copy of self scaled by a given factor.

        Parameter ``factor`` (float):
            Scaling factor.

        Returns → :class:`Surface`:
            Scaled copy of self.
        """
        if self.width == "auto":
            warnings.warn(
                ConfigWarning("Surface width set to 'auto', cannot be scaled")
            )
            new_width = self.width
        else:
            new_width = self.width * factor

        return attr.evolve(self, width=new_width)


class SurfaceFactory(BaseFactory):
    """
    This factory constructs objects whose classes are derived from :class:`Surface`.

    .. admonition:: Registered factory members
       :class: hint

       .. factorytable::
          :factory: SurfaceFactory
    """

    _constructed_type = Surface
    registry = {}
