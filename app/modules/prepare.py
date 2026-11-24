from app.business import DomainIssue, by_kind, prepared, single


def coverage(windows, meters, width):
    """缺测窗口的覆盖记录。

    每只注册分表是否到齐、缺少哪些表、已到读数逐条保留记录键，
    以便即使窗口不能参与峰值，窗口依据也不会随计算结果一起丢失。
    """
    records = []
    for start in sorted(windows):
        arrived = windows[start]
        missing = sorted(meters - arrived.keys())
        if not missing:
            continue
        readings = sorted(
            (
                {
                    "record": value["record"],
                    "meter": meter,
                    "minute": value["minute"],
                    "kw": value["kw"],
                }
                for meter, value in arrived.items()
            ),
            key=lambda item: (item["meter"], item["record"]),
        )
        records.append(
            {
                "window_start_min": start,
                "window_end_min": start + width,
                "required_meters": sorted(meters),
                "arrived_meters": sorted(arrived),
                "missing_meters": missing,
                "arrived_total": sum(value["kw"] for value in arrived.values()),
                "readings": readings,
            }
        )
    return records


def prepare(rows):
    invoice = single(rows, "invoice")
    width = invoice["window_min"]
    meters = {r["meter"] for r in by_kind(rows, "meter")}
    windows = {}
    if not width or len(meters) != invoice["required"] or not meters:
        raise DomainIssue("METER_CONTRACT")
    for r in by_kind(rows, "reading"):
        if r["meter"] not in meters:
            raise DomainIssue("UNKNOWN_METER")
        start = r["minute"] // width * width
        window = windows.setdefault(start, {})
        if r["meter"] in window and window[r["meter"]]["kw"] != r["kw"]:
            raise DomainIssue("METER_CONFLICT")
        window[r["meter"]] = r
    totals = {
        start: sum(value["kw"] for value in window.values())
        for start, window in windows.items()
        if window.keys() == meters
    }
    covered = coverage(windows, meters, width)
    if not totals:
        raise DomainIssue("NO_COMPLETE_WINDOW", {"coverage": covered})
    return prepared(
        len(totals),
        {
            "incomplete_windows": len(covered),
            "window_min": width,
            "coverage": covered,
        },
        (totals, invoice["kw"], covered),
    )
