"""Bounded per-host events. Files are controller artifacts, not remote paths."""
import json
import os
import re
from pathlib import Path

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = r'''
name: sre_result
type: stdout
short_description: Save fixed SRE execution events
description: Bounded result capture for the SRE Toolkit controller.
'''


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "sre_result"

    def event(self, result, failed=False, unreachable=False):
        host = result._host.get_name()
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", host):
            raise ValueError("invalid host alias")
        executing = result._task.get_name() == "SRE_EXECUTE"
        if not (executing or failed or unreachable):
            return
        data = result._result
        path = Path(os.environ["SRE_EVENT_DIR"]) / (host + ".json")
        # Keep the execution outcome but surface failed cleanup separately.
        if path.exists() and not executing:
            old = json.loads(path.read_text(encoding="utf-8"))
            old["cleanup_error"] = True
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(old, ensure_ascii=True), encoding="utf-8")
            os.replace(temporary, path)
            return
        payload = dict(executing=executing, failed=failed, unreachable=unreachable,
                       rc=data.get("rc"), stdout=str(data.get("stdout", ""))[:1048576],
                       stderr=str(data.get("stderr", ""))[:32768], message=str(data.get("msg", ""))[:32768])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        os.replace(temporary, path)
        self._display.display("SRE result received: " + host)

    def v2_runner_on_ok(self, result):
        self.event(result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.event(result, failed=True)

    def v2_runner_on_unreachable(self, result):
        self.event(result, unreachable=True)
