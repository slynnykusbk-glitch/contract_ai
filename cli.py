import argparse
import json
import sys
from pathlib import Path

from insurance_checker import check_file


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py")
    sub = parser.add_subparsers(dest="command")

    check_parser = sub.add_parser("check", help="Validate insurance requirements")
    check_parser.add_argument("path", help="Path to contract text file")

    args = parser.parse_args(argv)

    if args.command == "check":
        try:
            result = check_file(args.path)
        except Exception as exc:  # pragma: no cover
            print(json.dumps({"error": str(exc)}))
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["summary"]["hard_fail_count"] == 0 else 2
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
