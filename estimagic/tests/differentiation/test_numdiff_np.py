from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numdifftools import Gradient
from numdifftools import Jacobian
from numpy.testing import assert_array_almost_equal as aaae

from estimagic.differentiation.numdiff_np import _consolidate_one_step_derivatives
from estimagic.differentiation.numdiff_np import _get_output_shape
from estimagic.differentiation.numdiff_np import _nan_skipping_batch_evaluator
from estimagic.differentiation.numdiff_np import first_derivative
from estimagic.examples.numdiff_example_functions_np import logit_loglike
from estimagic.examples.numdiff_example_functions_np import logit_loglike_gradient
from estimagic.examples.numdiff_example_functions_np import logit_loglikeobs
from estimagic.examples.numdiff_example_functions_np import logit_loglikeobs_jacobian


@pytest.fixture
def binary_choice_inputs():
    fix_path = Path(__file__).resolve().parent / "binary_choice_inputs.pickle"
    inputs = pd.read_pickle(fix_path)
    return inputs


methods = ["forward", "backward", "central"]


@pytest.mark.parametrize("method", methods)
def test_first_derivative_jacobian(binary_choice_inputs, method):
    fix = binary_choice_inputs
    func = partial(logit_loglikeobs, y=fix["y"], x=fix["x"])

    calculated = first_derivative(
        func=func,
        method=method,
        x=fix["params_np"],
        n_steps=1,
        base_steps=None,
        lower_bounds=np.full(fix["params_np"].shape, -np.inf),
        upper_bounds=np.full(fix["params_np"].shape, np.inf),
        min_steps=1e-8,
        step_ratio=2.0,
        f0=func(fix["params_np"]),
        n_cores=1,
    )

    expected = logit_loglikeobs_jacobian(fix["params_np"], fix["y"], fix["x"])

    aaae(calculated, expected, decimal=6)


def test_first_derivative_jacobian_works_at_defaults(binary_choice_inputs):
    fix = binary_choice_inputs
    func = partial(logit_loglikeobs, y=fix["y"], x=fix["x"])
    calculated = first_derivative(func=func, x=fix["params_np"])
    expected = logit_loglikeobs_jacobian(fix["params_np"], fix["y"], fix["x"])
    aaae(calculated, expected, decimal=6)


@pytest.mark.parametrize("method", methods)
def test_first_derivative_gradient(binary_choice_inputs, method):
    fix = binary_choice_inputs
    func = partial(logit_loglike, y=fix["y"], x=fix["x"])

    calculated = first_derivative(
        func=func,
        method=method,
        x=fix["params_np"],
        n_steps=1,
        f0=func(fix["params_np"]),
        n_cores=1,
    )

    expected = logit_loglike_gradient(fix["params_np"], fix["y"], fix["x"])

    aaae(calculated, expected, decimal=4)


@pytest.mark.parametrize("method", methods)
def test_first_derivative_scalar(method):
    def f(x):
        return x ** 2

    calculated = first_derivative(f, 3.0)
    expected = 6.0
    aaae(calculated, expected)


def test_get_output_shape():
    a = [np.nan, 7, np.ones((3, 4)), 5]
    assert _get_output_shape(a) == (3, 4)


def test_nan_skipping_batch_evaluator():
    arglist = [np.nan, np.ones(2), np.array([3, 4]), np.nan, np.array([1, 2])]
    expected = [
        np.full(2, np.nan),
        np.ones(2),
        np.array([9, 16]),
        np.full(2, np.nan),
        np.array([1, 4]),
    ]
    calculated = _nan_skipping_batch_evaluator(lambda x: x ** 2, arglist, 1)
    for arr_calc, arr_exp in zip(calculated, expected):
        if np.isnan(arr_exp).all():
            assert np.isnan(arr_calc).all()
        else:
            aaae(arr_calc, arr_exp)


def test_consolidate_one_step_derivatives():
    forward = np.ones((1, 4, 3))
    forward[:, :, 0] = np.nan
    backward = np.zeros_like(forward)

    calculated = _consolidate_one_step_derivatives(
        {"forward": forward, "backward": backward}, ["forward", "backward"]
    )
    expected = np.array([[0, 1, 1]] * 4)
    aaae(calculated, expected)


@pytest.fixture()
def example_function_gradient_fixtures():
    def f(x):
        """f:R^3 -> R"""
        x1, x2, x3 = x[0], x[1], x[2]
        y1 = np.sin(x1) + np.cos(x2) + x3 - x3
        return y1

    def fprime(x):
        """Gradient(f)(x):R^3 -> R^3"""
        x1, x2, x3 = x[0], x[1], x[2]
        grad = np.array([np.cos(x1), -np.sin(x2), x3 - x3])
        return grad

    return {"func": f, "func_prime": fprime}


@pytest.fixture()
def example_function_jacobian_fixtures():
    def f(x):
        """f:R^3 -> R^2"""
        x1, x2, x3 = x[0], x[1], x[2]
        y1, y2 = np.sin(x1) + np.cos(x2), np.exp(x3)
        return np.array([y1, y2])

    def fprime(x):
        """Jacobian(f)(x):R^3 -> R^(2x3)"""
        x1, x2, x3 = x[0], x[1], x[2]
        jac = np.array([[np.cos(x1), -np.sin(x2), 0], [0, 0, np.exp(x3)]])
        return jac

    return {"func": f, "func_prime": fprime}


def test_first_derivative_gradient_richardson(example_function_gradient_fixtures):
    f = example_function_gradient_fixtures["func"]
    fprime = example_function_gradient_fixtures["func_prime"]

    true_grad = fprime(np.ones(3))
    numdifftools_grad = Gradient(f, order=2, n=3, method="central")(np.ones(3))
    grad = first_derivative(f, np.ones(3), n_steps=3, method="central")

    aaae(numdifftools_grad, grad)
    aaae(true_grad, grad)


def test_first_derivative_jacobian_richardson(example_function_jacobian_fixtures):
    f = example_function_jacobian_fixtures["func"]
    fprime = example_function_jacobian_fixtures["func_prime"]

    true_grad = fprime(np.ones(3))
    numdifftools_grad = Jacobian(f, order=2, n=3, method="central")(np.ones(3))
    grad = first_derivative(f, np.ones(3), n_steps=3, method="central")

    aaae(numdifftools_grad, grad)
    aaae(true_grad, grad)
