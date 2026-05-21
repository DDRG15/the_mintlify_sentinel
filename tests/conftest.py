import os
import shutil
import pytest

_OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output",
    "changelog.mdx",
)


@pytest.fixture(autouse=True, scope="session")
def preserve_changelog():
    """
    Save output/changelog.mdx before the test session starts and restore it
    after all tests finish. Prevents test runs from permanently overwriting
    the changelog produced by the last real pipeline run.
    """
    backup = _OUTPUT_FILE + ".bak"

    if os.path.exists(_OUTPUT_FILE):
        shutil.copy2(_OUTPUT_FILE, backup)

    yield

    if os.path.exists(backup):
        shutil.move(backup, _OUTPUT_FILE)
    elif os.path.exists(_OUTPUT_FILE):
        os.unlink(_OUTPUT_FILE)
