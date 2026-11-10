import inspect

import main


def test_main_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(main.main)
