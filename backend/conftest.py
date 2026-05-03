import asyncio
import inspect


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark a test as asynchronous")


def pytest_pyfunc_call(pyfuncitem):
    testfunction = pyfuncitem.obj
    if inspect.iscoroutinefunction(testfunction):
        funcargs = {
            name: pyfuncitem.funcargs[name]
            for name in pyfuncitem._fixtureinfo.argnames
        }
        asyncio.run(testfunction(**funcargs))
        return True
