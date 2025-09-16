from __future__ import annotations

import argparse
import os

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["access", "export", "erasure"])
    parser.add_argument("identifier")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True)
    parser.add_argument("--api-key", dest="api_key", default=os.getenv("API_KEY", ""))
    args = parser.parse_args()

    url = f"{args.base}/api/dsar/{args.action}"
    headers = {"x-api-key": args.api_key}
    params = {"identifier": args.identifier, "token": args.token}
    if args.action == "erasure":
        resp = requests.post(url, headers=headers, params=params, timeout=30)
    else:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    print(resp.text)


if __name__ == "__main__":
    main()
