from fieldservice_service import _tenant_hostname


def test_tenant_slug_becomes_predictable_subdomain():
    assert _tenant_hostname("North_Wind", "dispatch.example.com") == "north-wind.dispatch.example.com"
