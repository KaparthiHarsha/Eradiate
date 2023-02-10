import typing as t
from collections import abc as cabc
from functools import lru_cache

import attrs
import mitsuba as mi
import numpy as np

from ._core import PhaseFunction, phase_function_factory
from ..core import BoundingBox, traverse
from ...attrs import documented
from ...contexts import KernelDictContext, SpectralContext
from ...kernel import InitParameter, UpdateParameter, map_unit_cube
from ...units import unit_context_kernel as uck


@attrs.define(eq=False, slots=False)
class BlendPhaseFunction(PhaseFunction):
    """
    Blended phase function [``blend_phase``].

    This phase function aggregates two or more sub-phase functions
    (*components*) and blends them based on its `weights` parameter. Weights are
    usually based on the associated medium's scattering coefficient.
    """

    components: t.List[PhaseFunction] = documented(
        attrs.field(
            converter=lambda x: [phase_function_factory.convert(y) for y in x],
            validator=attrs.validators.deep_iterable(
                attrs.validators.instance_of(PhaseFunction)
            ),
            kw_only=True,
        ),
        type="list of :class:`.PhaseFunction`",
        init_type="list of :class:`.PhaseFunction` or list of dict",
        doc="List of components (at least two). This parameter has not default.",
    )

    @components.validator
    def _components_validator(self, attribute, value):
        if not len(value) > 1:
            raise ValueError(
                f"while validating {attribute.name}: BlendPhaseFunction must "
                "have at least two components"
            )

    weights: t.Union[
        np.ndarray, t.List[t.Callable[[KernelDictContext], np.ndarray]]
    ] = documented(
        attrs.field(
            converter=lambda x: x if callable(x[0]) else np.array(x, dtype=np.float64),
            kw_only=True,
        ),
        type="ndarray or list of callables",
        init_type="array-like or list of callables",
        doc="List of weights associated with each component. Weights may be "
        "numerical values; in that case, they ust be of shape (n,) or (n, m), "
        "where n is the number of components and m the number of cells along "
        "the atmosphere's vertical axis. Alternatively, weights may be "
        "callables that take a :class:`.KernelDictContext` as argument and "
        "return an array of shape (n, m). "
        "This parameter is required and has no default.",
    )

    @weights.validator
    def _weights_validator(self, attribute, value):
        if isinstance(value, np.ndarray):
            if value.ndim == 0 or value.ndim > 2:
                raise ValueError(
                    f"while validating '{attribute.name}': array must have 1 or 2 "
                    f"dimensions, got {value.ndim}"
                )

            if not value.shape[0] == len(self.components):
                raise ValueError(
                    f"while validating '{attribute.name}': array must have shape "
                    "(n,) or (n, m) where n is the number of components; got "
                    f"{value.shape}"
                )

        elif isinstance(value, cabc.Sequence):
            if not len(value) == len(self.components):
                raise ValueError(
                    f"while validating '{attribute.name}': weight and component "
                    "lists must have the same length"
                )

    bbox: t.Optional[BoundingBox] = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(BoundingBox.convert),
            validator=attrs.validators.optional(
                attrs.validators.instance_of(BoundingBox)
            ),
        ),
        default="None",
        type=":class:`.BoundingBox` or None",
        init_type="quantity or array-like or :class:`.BoundingBox`, optional",
        doc="Optional bounding box describing the extent of the volume "
        "associated with this phase function. If a component is another "
        "blended phase function, its bounding box will be forced to match "
        "this one.",
    )

    def update(self) -> None:
        super().update()

        # Synchronise bounding boxes
        for component in self.components:
            component.update()

            if isinstance(component, BlendPhaseFunction):
                component.bbox = self.bbox

    def _gridvolume_transform(self) -> "mitsuba.ScalarTransform4f":
        if self.bbox is None:
            # This is currently possible because the bounding box is expected to
            # be set by a parent Atmosphere object based on the selected
            # geometry
            raise ValueError(
                "computing the gridvolume transform requires a bounding box"
            )

        length_units = uck.get("length")
        bbox_min = self.bbox.min.m_as(length_units)
        bbox_max = self.bbox.max.m_as(length_units)

        return map_unit_cube(
            xmin=bbox_min[0],
            xmax=bbox_max[0],
            ymin=bbox_min[1],
            ymax=bbox_max[1],
            zmin=bbox_min[2],
            zmax=bbox_max[2],
        )

    @lru_cache(maxsize=1)
    def _eval_conditional_weights_impl(self, sctx: SpectralContext) -> np.ndarray:
        """
        Memoised weight evaluation, used if weights are defined as callables.
        """
        n_comp = len(self.components)

        if isinstance(self.weights, list):
            weights = np.array([w(sctx) for w in self.weights], dtype=np.float64)
        else:  # if isinstance(self.weights, np.ndarray):
            weights = np.array(self.weights, dtype=np.float64)

        if weights.ndim < 2:
            weights = weights.reshape((-1, 1))

        result = np.zeros((n_comp - 1, *weights.shape[1:]), dtype=np.float64)

        # Compute conditional weights
        for i in range(n_comp - 1):
            # Normalise weights
            weights_sum = weights[i:, ...].sum(axis=0, keepdims=True)
            weights_normalized = np.divide(
                weights[i:, ...],
                weights_sum,
                where=weights_sum != 0.0,
                out=np.zeros_like(weights[i:, ...]),
            )
            # Aggregate weights of all components except the first one
            result[i] = weights_normalized[1:, ...].sum(axis=0, keepdims=True)

        return result

    def eval_conditional_weights(
        self,
        sctx: SpectralContext,
        n_component: t.Union[int, t.List[int], None] = None,
    ) -> np.ndarray:
        """
        Evaluate the conditional weights of specified Mitsuba phase function
        components.

        Parameters
        ----------
        sctx : :class:`.SpectralContext`
            Spectral context.

        n_component : int or list of int, optional
            The index of the Mitsuba phase function component for which the
            conditional weight should be evaluated. If ``None``, the conditional
            weights of all components will be evaluated.

        Returns
        -------
        ndarray
            Conditional weights of the specified components as an array of shape
            (N, M) where n is the number of components and m the number of cells
            along the atmosphere's vertical axis.
        """
        if n_component is None:
            n_component = range(len(self.components) - 1)
        elif isinstance(n_component, int):
            n_component = [n_component]

        # Compute normalised component weights (cached until call with different context)
        weights = self._eval_conditional_weights_impl(sctx)

        # Return selected components
        return weights[n_component, ...]

    @property
    def template(self) -> dict:
        result = {"type": "blendphase"}

        for i in range(len(self.components) - 1):
            prefix = "phase_1." * i

            # Add components
            template, _ = traverse(self.components[i])
            result.update(
                {
                    **{f"{prefix}phase_0.{k}": v for k, v in template.items()},
                    f"{prefix}phase_1.type": "blendphase",
                }
            )

            # Assign conditional weight to second component
            result[f"{prefix}weight.type"] = "gridvolume"

            # Note: This defines a partial and evaluates the component index.
            # Passing i as the kwarg default value is essential to force the
            # dereferencing of the loop variable.
            def eval_conditional_weights(ctx: KernelDictContext, n_component=i):
                return mi.VolumeGrid(
                    np.reshape(
                        self.eval_conditional_weights(ctx.spectral_ctx, n_component),
                        (-1, 1, 1),  # Mind dim ordering! (C-style, i.e. zyx)
                    ).astype(np.float32)
                )

            result[f"{prefix}weight.grid"] = InitParameter(eval_conditional_weights)

            if self.bbox is not None:
                result[f"{prefix}weight.to_world"] = self._gridvolume_transform()

        else:
            template, _ = traverse(self.components[-1])
            result.update({**{f"{prefix}phase_1.{k}": v for k, v in template.items()}})

        return result

    @property
    def params(self) -> t.Dict[str, UpdateParameter]:
        result = {}

        for i in range(len(self.components) - 1):
            prefix = "phase_1." * i

            # Add components
            _, params = traverse(self.components[i])
            result.update(
                {
                    **{f"{prefix}phase_0.{k}": v for k, v in params.items()},
                }
            )

            # Note: This defines a partial and evaluates the component index.
            # Passing i as the kwarg default value is essential to force the
            # dereferencing of the loop variable.
            def eval_conditional_weights(ctx: KernelDictContext, n_component=i):
                return np.reshape(
                    self.eval_conditional_weights(ctx.spectral_ctx, n_component),
                    (-1, 1, 1, 1),  # Mind dim ordering! (C-style, i.e. zyxc)
                ).astype(np.float32)

            # Assign conditional weight to second component
            result[f"{prefix}weight.data"] = UpdateParameter(
                eval_conditional_weights, UpdateParameter.Flags.SPECTRAL
            )

        else:
            _, params = traverse(self.components[-1])
            result.update({**{f"{prefix}phase_1.{k}": v for k, v in params.items()}})

        return result
