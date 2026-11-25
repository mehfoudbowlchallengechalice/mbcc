"""Format the non-secret, flat env.yaml as additive gcloud environment updates."""
import json
import re
import sys
from pathlib import Path

DELIMITER = "@MBCC@"


def config_updates(path):
    settings = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in settings:
            raise ValueError("Use unique environment setting names in env.yaml.")
        if re.fullmatch(r"MBCC_.+_KEYWORD", key):
            raise ValueError("Configure private keywords directly in Cloud Run, outside env.yaml.")
        if raw.startswith('"'):
            try:
                value, end = json.JSONDecoder().raw_decode(raw)
            except ValueError:
                raise ValueError("Use quoted string values in env.yaml.") from None
            remainder = raw[end:].strip()
            if remainder and not remainder.startswith("#"):
                raise ValueError("Invalid content after a setting in env.yaml.")
        else:
            match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", raw)
            if not match:
                raise ValueError("Use quoted string values in env.yaml.")
            value = match[1].replace("''", "'")
        if not isinstance(value, str) or DELIMITER in value or "\n" in value or "\r" in value:
            raise ValueError("Unsupported environment setting format.")
        settings[key] = value
    if not settings:
        raise ValueError("No deployment settings found in env.yaml.")
    return "^" + DELIMITER + "^" + DELIMITER.join(f"{key}={value}" for key, value in settings.items())


if __name__ == "__main__":
    try:
        print(config_updates(sys.argv[1]))
    except ValueError as error:
        raise SystemExit(str(error)) from None
