#!/usr/bin/env python3
import os, json, csv, math

INPUT_DIR = "Results/Logs"
HOSTS     = [5, 6, 7, 8]  # process server_h5.json … server_h8.json

for h in HOSTS:
    in_json = os.path.join(INPUT_DIR, f"server_h{h}.json")
    out_csv = os.path.join(INPUT_DIR, f"server_h{h}_normalized.csv")
    if not os.path.exists(in_json):
        print(f"[!] missing {in_json}, skipping")
        continue

    with open(in_json) as fin, open(out_csv, "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["time", "actual_mbps", "demanded_mbps", "loss_pct"])

        buf = ""
        depth = 0
        row_idx = 0

        for line in fin:
            # Accumulate full JSON objects by tracking braces
            depth += line.count("{") - line.count("}")
            buf += line

            if depth == 0 and buf.strip():
                try:
                    rec = json.loads(buf)
                except json.JSONDecodeError:
                    buf = ""
                    continue

                # Emit one row per *full‐second* interval only
                for iv in rec.get("intervals", []):
                    s   = iv["sum"]
                    dur = s.get("seconds", 0.0)
                    # skip any interval that isn't ~1 s long
                    if dur < 0.99 or dur > 1.01:
                        continue

                    bps           = s["bits_per_second"]
                    loss_p        = s.get("lost_percent", 0.0)
                    actual_mbps   = bps / 1e6
                    demanded_mbps = actual_mbps * (1 + loss_p / 100)

                    row_idx += 1
                    writer.writerow([
                        row_idx,
                        f"{actual_mbps:.3f}",
                        f"{demanded_mbps:.3f}",
                        f"{loss_p:.3f}"
                    ])

                buf = ""  # reset buffer for next JSON object

    print(f"Wrote {out_csv}")
