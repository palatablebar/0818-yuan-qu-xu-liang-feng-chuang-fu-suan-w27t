import io
import json

import pytest

from app.business import DomainIssue
from app.evidence.render import artifact
from app.modules.pipeline import run
from app.review.service import execute, review
from conftest import csv_data

METER_ONE = ["m1", "0009", "meter", "0", "1", "0", "0", "0", "底稿"]
METER_TWO = ["m2", "0009", "meter", "0", "2", "0", "0", "0", "底稿"]
INVOICE = ["i1", "0009", "invoice", "0", "0", "40", "15", "2", "明细"]
READ_ONE = ["r1", "0009", "reading", "0", "1", "10", "0", "0", "已到"]
READ_TWO = ["r2", "0009", "reading", "5", "2", "30", "0", "0", "已到"]


def source(partial):
    """返回含一个完整窗口（合计 40）和一个缺表窗口的来源。"""
    rows = [
        INVOICE,
        METER_ONE,
        METER_TWO,
        READ_ONE,
        READ_TWO,
        ["r3", "0009", "reading", "35", "1", str(partial), "0", "0", "缺测窗已到"],
    ]
    return csv_data(rows)


def find(data, code="0009"):
    return next(c for c in run(data, 4)["cases"] if c["case"] == code)


def test_incomplete_window_keeps_coverage_when_not_blocking():
    item = find(source(10))
    assert item["status"] == "READY"
    assert item["measure"]["value"] == 40
    assert item["measure"]["flag"] == "INCOMPLETE_WINDOW"
    assert item["measure"]["blocking"] == []
    (window,) = item["coverage"]
    assert (window["window_start_min"], window["window_end_min"]) == (30, 45)
    assert window["required_meters"] == [1, 2]
    assert window["arrived_meters"] == [1]
    assert window["missing_meters"] == [2]
    assert window["arrived_total"] == 10
    assert [reading["record"] for reading in window["readings"]] == ["r3"]


def test_incomplete_window_survives_without_complete_windows():
    rows = [
        INVOICE,
        METER_ONE,
        METER_TWO,
        ["r1", "0009", "reading", "0", "1", "10", "0", "0", "已到"],
        ["r2", "0009", "reading", "20", "1", "20", "0", "0", "已到"],
    ]
    item = find(csv_data(rows))
    assert item["status"] == "NO_COMPLETE_WINDOW"
    assert {window["window_start_min"] for window in item["coverage"]} == {0, 15}
    assert [window["missing_meters"] for window in item["coverage"]] == [[2], [2]]
    assert [window["arrived_total"] for window in item["coverage"]] == [10, 20]


def test_missing_window_alone_is_recorded_for_every_partial_window():
    item = find(source(10))
    assert len(item["coverage"]) == 1 and item["prep"]["details"]["incomplete_windows"] == 1


def test_prepare_stage_already_exposes_coverage():
    item = next(c for c in run(source(10), 2)["cases"] if c["case"] == "0009")
    assert item["coverage"][0]["missing_meters"] == [2]
    assert item["prep"]["details"]["coverage"] == item["coverage"]


def test_partial_reading_at_candidate_peak_blocks():
    item = find(source(40))
    assert item["status"] == "READY" and item["measure"]["value"] == 40
    assert item["measure"]["flag"] == "BLOCKED_INCOMPLETE_WINDOW"
    assert item["measure"]["blocking"] == [
        {
            "window_start_min": 30,
            "window_end_min": 45,
            "arrived_total": 40,
            "missing_meters": [2],
            "records": ["r3"],
        }
    ]


def test_partial_reading_above_candidate_peak_blocks():
    item = find(source(99))
    assert item["measure"]["flag"] == "BLOCKED_INCOMPLETE_WINDOW"


def test_approval_blocked_with_case_and_records(store):
    run = execute(store, source(40))
    with pytest.raises(DomainIssue) as caught:
        review(store, run["id"], dict(revision=0, status="APPROVED", note="确认无误"))
    assert caught.value.code == "UNRESOLVED_ISSUES"
    blocking = caught.value.details["blocking"]
    assert [item["case"] for item in blocking] == ["0009"]
    assert blocking[0]["records"] == ["r3"]


def test_approval_allowed_with_coverage_scope(store):
    run = execute(store, source(10))
    output = review(
        store, run["id"], dict(revision=0, status="APPROVED", note="覆盖范围已确认")
    )
    assert output["status"] == "APPROVED"


def test_rerun_does_not_add_batch_or_overwrite_evidence(store):
    data = source(40)
    run = execute(store, data)
    review(store, run["id"], dict(revision=0, status="HELD", note="等待补表"))
    again = execute(store, data)
    assert again["id"] == run["id"] and len(store.list()) == 1
    assert (again["status"], again["revision"], again["note"]) == ("HELD", 1, "等待补表")


def test_evidence_exports_coverage_and_blocking(store):
    packet = json.loads(artifact(execute(store, source(40))))
    case = next(item for item in packet["cases"] if item["case"] == "0009")
    assert case["coverage"][0]["missing_meters"] == [2]
    assert packet["balance"]["blocking"][0]["records"] == ["r3"]
    assert packet["balance"]["releasable"] is False


def test_blocked_http_response_names_case_and_records(client):
    run = client.post(
        "/api/runs", data={"file": (io.BytesIO(source(40)), "input.csv")}
    ).json
    response = client.patch(
        f"/api/runs/{run['id']}",
        json=dict(revision=0, status="APPROVED", note="确认无误"),
    )
    assert response.status_code == 409 and response.json["code"] == "UNRESOLVED_ISSUES"
    assert "0009" in response.json["message"] and "r3" in response.json["message"]
    assert response.json["details"]["blocking"][0]["records"] == ["r3"]


def test_clean_sample_can_be_issued_with_coverage_scope(store, clean):
    run = execute(store, clean)
    case = next(item for item in run["report"]["cases"] if item["case"] == "0001")
    assert (case["coverage"][0]["missing_meters"], case["coverage"][0]["arrived_total"]) == ([2], 5)
    assert run["report"]["balance"]["releasable"] is True
    assert review(
        store, run["id"], dict(revision=0, status="APPROVED", note="覆盖范围已确认")
    )["status"] == "APPROVED"


def test_dirty_sample_names_blocking_case_and_record(store, dirty):
    run = execute(store, dirty)
    with pytest.raises(DomainIssue) as caught:
        review(store, run["id"], dict(revision=0, status="APPROVED", note="核对完成"))
    blocking = caught.value.details["blocking"]
    assert [(item["case"], item["records"]) for item in blocking] == [
        ("0001", ["000108"])
    ]
