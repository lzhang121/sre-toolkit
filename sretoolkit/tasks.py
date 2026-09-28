"""Closed task registry. Parameters are data, never executable configuration."""
import re
from urllib.parse import urlsplit

from sretoolkit import VERSION

TASKS = {
    "system": {"params": {}, "kind": "check"},
    "storage": {"params": {}, "kind": "check"},
    "processes": {"params": {}, "kind": "check"},
    "network": {"params": {}, "kind": "check"},
    "logs": {"params": {}, "kind": "check"},
    "directory": {"params": {"path": "path"}, "kind": "check"},
    "service_status": {"params": {"service": "service"}, "kind": "check"},
    "dns": {"params": {"host": "host"}, "kind": "check"},
    "tcp": {"params": {"host": "host", "port": "port"}, "kind": "check"},
    "http": {"params": {"url": "url"}, "kind": "check"},
    "journal": {"params": {"service": "service", "minutes": "minutes"}, "kind": "check"},
    "access_log": {"params": {"path": "path"}, "kind": "legacy"},
    "service": {"params": {"service": "service", "action": "action"}, "kind": "maintenance"},
    "backup": {"params": {"source": "path"}, "kind": "maintenance", "timeout": 900},
    "cleanup": {"params": {"directory": "path", "days": "days"}, "kind": "maintenance"},
}
BASIC = ["system", "storage", "processes", "network", "logs"]
for _task in TASKS.values():
    _task.setdefault("timeout", 60)
    _task["privileged"] = _task["kind"] == "maintenance"
    _task["exit_codes"] = {"0": "ok", "1": "warning", "2": "error"} if not _task["privileged"] else {"0": "ok", "other": "error"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("invalid identifier")
    return value


def validate(task, params):
    if task not in TASKS or not isinstance(params, dict):
        raise ValueError("unknown task or invalid parameters")
    schema = TASKS[task]["params"]
    if set(params) != set(schema):
        raise ValueError("parameters must be exactly: " + ", ".join(schema))
    validated = {}
    for name, kind in schema.items():
        value = params[name]
        if kind in {"port", "minutes", "days"}:
            maximum = {"port": 65535, "minutes": 1440, "days": 36500}[kind]
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(name + " out of range")
        else:
            if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
                raise ValueError("invalid " + name)
            if kind == "path" and (not value.startswith("/") or ".." in value.split("/")):
                raise ValueError("path must be absolute and cannot contain ..")
            if kind == "service" and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]{0,127}", value):
                raise ValueError("invalid service")
            if kind == "host" and not re.fullmatch(r"[A-Za-z0-9_:][A-Za-z0-9_.:%-]{0,252}", value):
                raise ValueError("invalid host")
            if kind == "action" and value not in {"start", "stop", "restart"}:
                raise ValueError("invalid action")
            if kind == "url":
                url = urlsplit(value)
                if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.fragment:
                    raise ValueError("HTTP(S) URL required; credentials and fragments forbidden")
        validated[name] = value
    return validated


def catalogue():
    return {"version": VERSION, "basic": BASIC, "tasks": TASKS}
