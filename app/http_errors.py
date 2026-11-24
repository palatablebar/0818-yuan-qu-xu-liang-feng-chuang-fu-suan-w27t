from flask import jsonify

LABELS = {
    "FILE_TOO_LARGE": "文件超过 256 KiB",
    "FILE_EMPTY": "文件没有内容",
    "FILE_BLANK": "文件只有空白",
    "HEADER_ONLY": "文件只有标题行",
    "HEADER_MISMATCH": "列名与字段字典不一致",
    "ENCODING_INVALID": "请使用 UTF-8 CSV",
    "CSV_MALFORMED": "CSV 引号或行格式异常",
    "ROW_LIMIT": "文件超过 2000 行",
    "FILE_REQUIRED": "请选择 CSV 文件",
    "RUN_NOT_FOUND": "批次不存在",
    "REVIEW_FIELDS": "请填写 3 至 200 字复核意见",
    "STALE_REVIEW": "批次已更新，请刷新",
    "RUN_FINALIZED": "批次已签发",
    "UNRESOLVED_ISSUES": "存在待处理差异",
    "SAMPLE_UNKNOWN": "样例不存在",
    "STAGE_UNKNOWN": "处理阶段不存在",
}


def describe(error):
    """把阻断签发的分组与记录写进可读信息，便于原样交接。"""
    blocking = (getattr(error, "details", None) or {}).get("blocking") or []
    if error.code == "UNRESOLVED_ISSUES" and blocking:
        parts = []
        for item in blocking:
            records = "、".join(item.get("records") or []) or "—"
            parts.append(f"分组 {item.get('case')} 缺测窗口已到读数达到峰值（记录 {records}）")
        return "存在待处理差异 · " + "；".join(parts)
    return LABELS.get(error.code, error.code)


def response(error):
    code = error.code
    status = (
        404
        if code in {"RUN_NOT_FOUND", "SAMPLE_UNKNOWN", "STAGE_UNKNOWN"}
        else (
            409
            if code in {"STALE_REVIEW", "RUN_FINALIZED", "UNRESOLVED_ISSUES"}
            else 413 if code == "FILE_TOO_LARGE" else 422
        )
    )
    payload = dict(code=code, message=describe(error))
    if getattr(error, "details", None):
        payload["details"] = error.details
    return jsonify(payload), status
