from app.business import measured


def compute(data):
    totals, target, coverage = data
    time = max(totals, key=lambda k: (totals[k], -k))
    peak = totals[time]
    windows = []
    for item in coverage:
        windows.append(
            dict(
                item,
                blocking=item["arrived_total"] >= peak,
            )
        )
    blocking = [
        {
            "window_start_min": item["window_start_min"],
            "window_end_min": item["window_end_min"],
            "arrived_total": item["arrived_total"],
            "missing_meters": item["missing_meters"],
            "records": [reading["record"] for reading in item["readings"]],
        }
        for item in windows
        if item["blocking"]
    ]
    if blocking:
        flag = "BLOCKED_INCOMPLETE_WINDOW"
    elif windows:
        flag = "INCOMPLETE_WINDOW"
    else:
        flag = None
    result = measured(
        peak,
        target,
        "千瓦",
        {"peak_start_min": time, "windows": totals},
        flag=flag,
    )
    result["coverage"] = windows
    result["blocking"] = blocking
    return result
