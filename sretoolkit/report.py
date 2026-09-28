"""Complete a fixed execution matrix; render untrusted host output as text."""
import csv
import html
import json
from collections import Counter
from pathlib import Path

from sretoolkit.common import OUTPUT_LIMIT, STATUSES, result, write_json


def transport_records(event, run_id, host, tasks, phase):
    """Never interpret missing output or a broken connection as success."""
    if event is None:
        state, message = "unknown", "no terminal result received"
    elif event.get("unreachable"):
        state = "unknown" if phase == "apply" and event.get("executing") else "unreachable"
        message = "SSH connection unavailable; operation state unconfirmed" if state == "unknown" else "SSH connection unavailable"
    elif event.get("failed") and not event.get("executing"):
        state, message = "error", "remote setup failed"
    elif event.get("executing"):
        try:
            records = json.loads(event.get("stdout", ""))
            if not isinstance(records, list) or len(records) != len(tasks):
                raise ValueError("invalid result count")
            by_task = {}
            for record in records:
                if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("run_id") != run_id or record.get("host") != host:
                    raise ValueError("result binding mismatch")
                required = {"task", "status", "exit_code", "started_at", "duration", "changed", "summary", "metrics", "artifact_refs"}
                if not required <= record.keys() or record["task"] not in tasks or record["task"] in by_task or record["status"] not in STATUSES:
                    raise ValueError("invalid task record")
                if not isinstance(record["summary"], str) or not isinstance(record["metrics"], dict):
                    raise ValueError("invalid result types")
                # Remote artifact paths are metadata only, never files to fetch.
                record["artifact_refs"] = []
                for field in ("stdout", "stderr"):
                    record[field] = str(record.get(field, ""))[:OUTPUT_LIMIT]
                if event.get("cleanup_error") and record["status"] in {"ok", "warning"}:
                    record.update(status="error", summary="task completed but remote staging cleanup failed")
                by_task[record["task"]] = record
            if event.get("rc") not in {0, 1, 2}:
                raise ValueError("unexpected transport exit")
            return [by_task[task] for task in tasks]
        except (ValueError, TypeError, KeyError):
            state, message = ("unknown" if phase == "apply" else "error"), "invalid or incomplete remote result"
            if event.get("rc") in {124, 137}:
                state, message = ("unknown" if phase == "apply" else "timeout"), "remote deadline exceeded"
    else:
        state, message = "unknown", "no execution result received"
    diagnostic = str((event or {}).get("message", (event or {}).get("stderr", "")))[:OUTPUT_LIMIT]
    return [result(run_id, host, task, state, message, changed=None if phase == "apply" else False, stderr=diagnostic) for task in tasks]


def build_status(records):
    if any(r["status"] in {"error", "unreachable", "timeout", "unknown"} for r in records):
        return "FAILURE"
    if any(r["status"] == "warning" for r in records):
        return "UNSTABLE"
    return "SUCCESS"


def safe_csv(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def render(directory, manifest, records):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "results.json", records)
    counts = dict(Counter(r["status"] for r in records))
    summary = dict(run_id=manifest["run_id"], commit=manifest["commit"], phase=manifest["phase"],
                   build_status=build_status(records), counts=counts)
    write_json(directory / "summary.json", summary)
    fields = ["host", "task", "status", "exit_code", "duration", "changed", "summary"]
    with (directory / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows([safe_csv(r.get(k, "")) for k in fields] for r in records)
    escape = lambda value: html.escape(str(value), quote=True)
    rows = []
    for r in records:
        detail = json.dumps(r.get("metrics", {}), ensure_ascii=False, indent=2)
        detail += "\n" + r.get("stdout", "") + "\n" + r.get("stderr", "")
        cells = "".join("<td>" + escape(r.get(k, "")) + "</td>" for k in fields)
        rows.append("<tr>" + cells + "<td><details><summary>Details</summary><pre>" + escape(detail) + "</pre></details></td></tr>")
    document = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SRE execution report</title>
<style>body{font:15px system-ui;margin:24px;color:#17212b}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:700px}th{background:#eef3f7}</style>
<h1>SRE execution report</h1><pre>""" + escape(json.dumps(summary, ensure_ascii=False, indent=2))
    document += "</pre><table><thead><tr>" + "".join("<th>" + escape(k) + "</th>" for k in fields + ["details"])
    document += "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></html>"
    (directory / "index.html").write_text(document, encoding="utf-8")
    return summary
