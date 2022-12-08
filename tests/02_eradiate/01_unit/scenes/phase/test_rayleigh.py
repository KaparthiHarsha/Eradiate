import mitsuba as mi

from eradiate.contexts import KernelDictContext
from eradiate.scenes.core import NodeSceneElement, traverse
from eradiate.scenes.phase import PhaseFunction, RayleighPhaseFunction
from eradiate.test_tools.types import check_type


def test_rayleigh_type():
    check_type(
        RayleighPhaseFunction,
        expected_mro=[PhaseFunction, NodeSceneElement],
        expected_slots=[],
    )


def test_rayleigh(modes_all_double):
    # Default constructor
    phase = RayleighPhaseFunction()

    # Check if produced kernel dict can be instantiated
    template, params = traverse(phase)
    assert params.data == {}
    kernel_dict = template.render(ctx=KernelDictContext())
    assert isinstance(mi.load_dict(kernel_dict), mi.PhaseFunction)
