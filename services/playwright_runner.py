import asyncio
import os
from collections.abc import Callable
from typing import Any


def _run_in_dedicated_loop(async_callable: Callable[..., Any], args: tuple, kwargs: dict):
    """Ejecuta Playwright en un loop compatible con subprocesos en Windows.

    Uvicorn con --reload usa SelectorEventLoop en Windows. Ese loop no puede iniciar
    el proceso driver de Playwright, por eso se crea un ProactorEventLoop aislado.
    """
    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(async_callable(*args, **kwargs))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)


async def run_playwright_task(async_callable: Callable[..., Any], *args, **kwargs):
    """No bloquea el loop web y evita el NotImplementedError de subprocess en Windows."""
    return await asyncio.to_thread(_run_in_dedicated_loop, async_callable, args, kwargs)
