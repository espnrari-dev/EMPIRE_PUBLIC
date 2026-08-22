#!/usr/bin/env python3

import sys
import json
import time
import argparse
import requests


def query_crtsh(domain):
    url = f"https://crt.sh/?q=%25.{domain}&output=json"

    for attempt in range(3):
        try:
            r = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": "DeepRecon-Agent/1.0"
                }
            )

            if r.status_code != 200:
                continue

            data = r.json()

            results = set()

            for item in data:
                for name in item.get("name_value", "").split("\n"):
                    name = name.strip()

                    if (
                        name
                        and "*" not in name
                        and name.endswith(domain)
                    ):
                        results.add(name)

            return sorted(results)

        except Exception:
            time.sleep(2)

    return None


def query_hackertarget(domain):
    url = (
        "https://api.hackertarget.com/hostsearch/"
        f"?q={domain}"
    )

    try:
        r = requests.get(url, timeout=20)

        if r.status_code != 200:
            return []

        results = set()

        for line in r.text.splitlines():
            parts = line.split(",")

            if parts:
                host = parts[0].strip()

                if host.endswith(domain):
                    results.add(host)

        return sorted(results)

    except Exception:
        return []


def find_subdomains(domain):

    findings = set()

    crt_results = query_crtsh(domain)

    if crt_results:
        findings.update(crt_results)

    fallback = query_hackertarget(domain)

    if fallback:
        findings.update(fallback)

    return sorted(findings), crt_results is not None


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "domain"
    )

    args = parser.parse_args()

    start = time.time()

    subs, source_ok = find_subdomains(args.domain)

    output = {
        "tool": "piece_one_fixed",
        "target": args.domain,
        "count": len(subs),
        "subdomains": subs,
        "runtime": round(time.time() - start, 3),
        "status": "ok" if source_ok or subs else "error"
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
