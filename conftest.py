import pytest
import helpers

def pytest_configure(config):
    config.addinivalue_line("markers", "unittest: this marker is for unit tests.")
    config.addinivalue_line("markers", "integrtest: this marker is for integration test.")

@pytest.fixture
def git_repos():
    """
    Initialize a Git repository and make a single empty commit
    """
    helpers.run_git_cmd('init')
    helpers.run_git_cmd('commit --allow-empty -m "..."')    
    yield
    helpers.run_sys_cmd('rd /s /q .git')

@pytest.fixture
def temp_file():
    filename = "__temp_file.txt"
    helpers.run_sys_cmd('echo "content" >> {}'.format(filename))
    yield filename
    helpers.run_sys_cmd('del {}'.format(filename))

@pytest.fixture
def target_file():
    yield "SwPackageVersion.h"
    helpers.run_sys_cmd('del {}'.format("SwPackageVersion.h"))