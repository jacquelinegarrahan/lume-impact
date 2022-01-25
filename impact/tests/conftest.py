import pytest
from impact import Impact
import os

@pytest.fixture
def rootdir():
    return os.path.dirname(os.path.abspath(__file__))

@pytest.fixture
def impact_obj(rootdir):
    I = Impact(f'{rootdir}/files/awa_flatbeam/ImpactT.in')
    return I
