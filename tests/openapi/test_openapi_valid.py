import json
from openapi_spec_validator import validate_spec

def test_openapi_is_valid():
    with open('openapi.json') as f:
        spec = json.load(f)
    validate_spec(spec)
