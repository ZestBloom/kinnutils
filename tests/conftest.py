import os
import sys
import pytest

SOURCE_ROOT = os.path.normpath(os.path.join(__file__, "../../kinnutils"))
TEST_ROOT = os.path.normpath(os.path.join(__file__, ".."))

sys.path.insert(0, SOURCE_ROOT)
 

@pytest.fixture
def algodcli():
    from algorand.algoconn import get_algod
    
    return get_algod()


def pytest_addoption(parser):
    parser.addoption("--network", action="store", default="algorand")
    parser.addoption("--provider", action="store", default="testnet")
