import asyncio
from contextvars import copy_context
from functools import partial
from typing import Callable, TypeVar, cast

from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")

async def run_in_executor(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Run a function in an executor.

    Args:
        func (Callable[P, Output]): The function.
        *args (Any): The positional arguments to the function.
        **kwargs (Any): The keyword arguments to the function.

    Returns:
        Output: The output of the function.

    Raises:
        RuntimeError: If the function raises a StopIteration.
    """

    def wrapper() -> T:
        try:
            return func(*args, **kwargs)
        except StopIteration as exc:
            # StopIteration can't be set on an asyncio.Future
            # it raises a TypeError and leaves the Future pending forever
            # so we need to convert it to a RuntimeError
            raise RuntimeError from exc
    
    #TODO: Rethink of executor.
    return await asyncio.get_running_loop().run_in_executor(
        None,
        cast(Callable[..., T], partial(copy_context().run, wrapper)),
    )