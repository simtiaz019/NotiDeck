import pytest
from jinja2 import TemplateError
from notideck.routing import matches, render
from tests.conftest import send


@pytest.mark.parametrize(
    "condition,expected",
    [
        ({"field": "severity", "op": "gte", "value": "ERROR"}, True),
        ({"field": "severity", "op": "less", "value": "WARNING"}, False),
        ({"field": "metadata.lag", "op": "greater", "value": 100}, True),
        ({"field": "tags", "op": "contains", "value": "db"}, True),
        ({"field": "environment", "op": "in", "value": ["staging"]}, False),
        ({"field": "missing", "op": "exists", "value": False}, True),
        ({"field": "environment", "op": "not_equals", "value": "staging"}, True),
    ],
)
def test_conditions(condition, expected):
    assert (
        matches(
            {"severity": "CRITICAL", "metadata": {"lag": 120}, "tags": ["db"], "environment": "production"},
            [condition],
        )
        is expected
    )


def test_template_sandbox():
    assert render("{{ notification.title }}", {"title": "<script>"}, html=True) == "&lt;script&gt;"
    for template in [
        "{{ notification.__class__.__mro__ }}",
        "{{ range(100000000) }}",
        "{% for x in notification %}x{% endfor %}",
        '{{ "x" * 100000000 }}',
    ]:
        with pytest.raises((TemplateError, ValueError)):
            render(template, {"title": "safe"})


def test_overlapping_routes_deduplicate_and_simulate(client, scenario):
    response = client.post(
        "/api/v1/routes", json={"name": "Catchall", "targets": [{"channel_id": scenario["channel"]["id"]}]}
    )
    assert response.status_code == 201
    preview = client.post("/api/v1/routes/simulate", json={"title": "x", "message": "y"}).json()
    assert len(preview["rules"]) == 2
    assert len(preview["destinations"]) == 1
    assert client.get("/api/v1/queue").json()["total"] == 0
    send(client, scenario)
    assert client.get("/api/v1/queue").json()["total"] == 1


def test_group_expansion(client, scenario):
    recipient = client.post(
        "/api/v1/resources/recipients", json={"name": "DBA", "addresses": {"webhook": "destination"}}
    ).json()
    group = client.post(
        "/api/v1/resources/groups", json={"name": "DBAs", "members": [recipient["id"]]}
    ).json()
    rule = scenario["rule"]
    data = {
        k: rule[k]
        for k in [
            "name",
            "description",
            "enabled",
            "priority",
            "conditions",
            "targets",
            "stop",
            "template_id",
        ]
    }
    data["targets"] = [{"channel_id": scenario["channel"]["id"], "group_id": group["id"]}]
    assert client.patch("/api/v1/routes/" + rule["id"], json=data).status_code == 200
    assert send(client, scenario).status_code == 202
    assert client.get("/api/v1/queue").json()["items"][0]["recipient"] == "destination"


def test_stop_first_and_metadata_type_safety(client, scenario):
    first = client.post(
        "/api/v1/routes",
        json={
            "name": "Stop first",
            "priority": 0,
            "stop": True,
            "targets": [{"channel_id": scenario["channel"]["id"]}],
        },
    ).json()
    preview = client.post("/api/v1/routes/simulate", json={"title": "Test", "message": "Test"}).json()
    assert preview["rules"] == [{"id": first["id"], "name": "Stop first"}]
    assert not matches({"category": "database"}, [{"field": "category", "op": "contains", "value": 12}])
    assert not matches({"metadata": {}}, [{"field": "metadata", "op": "contains", "value": []}])
