import csv
import os

input_dir = "Results/Logs"
files = [f"server_h{i}.csv" for i in range(5, 9)]

for fname in files:
    input_path = os.path.join(input_dir, fname)
    output_path = os.path.join(input_dir, fname.replace(".csv", "_cleaned.csv"))

    if not os.path.exists(input_path):
        print(f"Skipping missing file: {input_path}")
        continue

    with open(input_path, "r") as infile, open(output_path, "w", newline="") as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        current_time = 0.0
        interval_length = 1.0
        last_stream = None
        last_client_port = None

        for row in reader:
            if len(row) < 7:
                writer.writerow(row)
                continue

            interval = row[6]
            stream_id = row[5]
            client_port = row[4]

            if interval.startswith("0.0-10"):
                continue

            # Detect start of a new connection
            if interval.startswith("0.0-") and (stream_id != last_stream or client_port != last_client_port):
                current_time = round(current_time, 1)
                last_stream = stream_id
                last_client_port = client_port

            # Skip summary intervals (e.g. 0.0-10.1)
            try:
                start_str, end_str = interval.split("-")
                float(start_str)  # validate format
                float(end_str)
                start = round(current_time, 1)
                end = round(start + interval_length, 1)
                row[6] = f"{start:.1f}-{end:.1f}"
                current_time = end
            except ValueError:
                # Likely a summary line or malformed, leave as-is
                pass

            writer.writerow(row)

    print(f"Processed: {output_path}")
