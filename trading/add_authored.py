"""Insert Claude-authored MCQs (source='claude', active). Reads a JSON array from stdin.

Each item: {"prompt": str, "options": [str, ...], "correct_index": int,
            "explanation"?: str, "subject"?: str}

Usage:  echo '[{...}]' | PYTHONPATH=. ./.venv-trading/bin/python -m trading.add_authored
"""
import json
import sys

from . import quiz


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, list):
        print("error: expected a JSON array of question objects", file=sys.stderr)
        sys.exit(1)
    n = quiz.add_authored(data)
    print(f"inserted {n} authored question(s)")


if __name__ == "__main__":
    main()
