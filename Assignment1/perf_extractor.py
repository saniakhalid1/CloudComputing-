import re
import csv

def parse_httperf_output(file_path, output_csv):
    with open(file_path, 'r') as f:
        data = f.read()

    # Split based on `httperf` calls followed by real results
    blocks = re.split(r'(?:^|\n)httperf --', data)[1:]  # skip first empty
    results = []

    for block in blocks:
        if "Total: connections" not in block:
            continue  # skip incomplete blocks

        run_data = {}

        # Rate
        rate_match = re.search(r'--rate=(\d+)', block)
        run_data['rate'] = int(rate_match.group(1)) if rate_match else 0

        # Total requests
        total_match = re.search(r'requests (\d+)', block)
        run_data['total_requests'] = int(total_match.group(1)) if total_match else 0

        # Replies (needed for unprocessed calculation)
        replies_match = re.search(r'replies (\d+)', block)
        total_replies = int(replies_match.group(1)) if replies_match else 0

        # 2xx replies
        processed_match = re.search(r'2xx=(\d+)', block)
        processed = int(processed_match.group(1)) if processed_match else 0
        run_data['processed_requests'] = processed
        run_data['unprocessed_requests'] = total_replies - processed

        # Average reply time
        reply_time_match = re.search(r'Reply time \[ms\]: response ([\d.]+)', block)
        run_data['avg_reply_time_ms'] = float(reply_time_match.group(1)) if reply_time_match else 0.0

        results.append(run_data)

    # Write final CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['rate', 'total_requests', 'processed_requests', 'unprocessed_requests', 'avg_reply_time_ms'])
        writer.writeheader()
        writer.writerows(results)

# Call function
parse_httperf_output('output.txt', 'httperf_summary.csv')
