from collections import Counter


def _windows(case):
    return (case.get("measure") or {}).get("blocking") or []


def _readings(windows):
    seen, records = set(), []
    for window in windows:
        for record in window["records"]:
            if record not in seen:
                seen.add(record)
                records.append(record)
    return records


def balance(intake, cases):
    accounted = (
        intake["accepted"] + intake["rejected"] + intake["blank"] + intake["repeated"]
    )
    status = Counter(case["status"] for case in cases)
    ready = status.pop("READY", 0)
    observed = sum(len(case["records"]) for case in cases)
    blocking = [
        {
            "case": case["case"],
            "records": _readings(windows),
            "case_records": list(case["records"]),
            "windows": windows,
        }
        for case in cases
        for windows in [_windows(case)]
        if windows
    ]
    coverage = [
        {"case": case["case"], "windows": case.get("coverage") or []}
        for case in cases
        if case.get("coverage")
    ]
    return dict(
        input=intake["input"],
        accepted=intake["accepted"],
        isolated=intake["rejected"],
        ignored=intake["blank"] + intake["repeated"],
        accounted=accounted,
        balanced=accounted == intake["input"] and observed == intake["accepted"],
        ready=ready,
        pending=len(cases) - ready,
        issues=dict(sorted(status.items())),
        coverage=coverage,
        blocking=blocking,
        releasable=bool(cases)
        and ready == len(cases)
        and not intake["rejected"]
        and accounted == intake["input"]
        and observed == intake["accepted"]
        and not blocking,
    )
