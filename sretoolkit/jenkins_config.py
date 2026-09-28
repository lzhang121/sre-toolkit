"""Export the few scalar fields Jenkins needs, without JSON parsing plugins."""
import argparse
import json
import sys
from pathlib import Path


def fields(kind, document, environment):
    if kind == "environment":
        settings = document["environments"][environment]
        values = {key: settings[key] for key in (
            "ssh_credential_id", "known_hosts_credential_id", "ssh_config_credential_id", "approvers")}
    else:
        hosts = document["hosts"]
        if not isinstance(hosts, list) or not hosts or not all(isinstance(host, str) for host in hosts):
            raise ValueError("approval hosts must be a nonempty string list")
        values = {key: document[key] for key in ("task", "run_id", "commit", "digest")}
        values["hosts"] = ", ".join(hosts)
    # The wire format is key<TAB>value per line. Reject control characters
    # rather than letting a value create additional fields in the pipeline.
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("missing or invalid field: " + key)
    return "\n".join(key + "\t" + value for key, value in values.items())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["environment", "approval"])
    parser.add_argument("file")
    parser.add_argument("environment", nargs="?", default="test")
    args = parser.parse_args(argv)
    try:
        document = json.loads(Path(args.file).read_text(encoding="utf-8"))
        print(fields(args.kind, document, args.environment))
        return 0
    except FileNotFoundError:
        print("Missing configuration file: " + args.file +
              ". For inventory, create configs/inventory.json from the example with real hosts and credential IDs.", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Invalid " + args.kind + " configuration: " + str(exc), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
