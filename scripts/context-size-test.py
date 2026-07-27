import csv
import io
import sys
import requests

API = "http://localhost:5000"

START_ROWS = 5
GROWTH_FACTOR = 2


def make_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "name", "value", "note"])
    for i in range(rows):
        w.writerow([i, f"item_{i}", i * 1.5, "some descriptive text here"])
    return buf.getvalue()


def parse_rows(text):
    return list(csv.reader(io.StringIO(text)))


def run_trial(rows):
    content = make_csv(rows)
    files = {"file": (f"test_{rows}.csv", content, "text/csv")}
    r = requests.post(f"{API}/csv", files=files, timeout=30)
    print(f"\nrows={rows} bytes={len(content)} upload_status={r.status_code}")
    if not r.ok:
        raise RuntimeError(f"upload failed at rows={rows}: {r.status_code} {r.text}")

    resp = requests.post(f"{API}/chat", json={"instruction": "Return this CSV completely unchanged."}, timeout=120)
    print("chat status:", resp.status_code)
    if not resp.ok:
        raise RuntimeError(f"chat failed at rows={rows}: {resp.status_code} {resp.text}")

    data = resp.json()
    returned = data.get("csv") or ""
    original_rows = parse_rows(content)
    returned_rows = parse_rows(returned)
    print(f"original_rows={len(original_rows)} returned_rows={len(returned_rows)} match={returned_rows == original_rows}")

    requests.delete(f"{API}/chat")  # reset session so history doesn't compound

    if returned_rows != original_rows:
        print("\n--- raw model response ---")
        print(data.get("response"))
        print("--- end raw response ---")
        for idx, (o, r) in enumerate(zip(original_rows, returned_rows)):
            if o != r:
                print(f"first differing row {idx}: original={o!r} returned={r!r}")
                break
        else:
            print(f"row count differs: original={len(original_rows)} returned={len(returned_rows)}")
        raise RuntimeError(f"round-trip mismatch at rows={rows}")


if __name__ == "__main__":
    rows = START_ROWS
    while True:
        try:
            run_trial(rows)
        except (RuntimeError, requests.exceptions.RequestException) as e:
            print(f"\nFAILED at rows={rows}: {e}")
            sys.exit(1)
        rows *= GROWTH_FACTOR
