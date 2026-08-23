#!/usr/bin/env python3
"""
CLI SMS sender for Clawdtalk.
Reads:
  - API keys from api_keys.txt (one per line)
  - Phone numbers from numbers.txt (one per line)
  - Messages from messages.txt (one per line)
Usage: python send_cli.py [--per-msg N] [--dry-run]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests


def read_lines(filename: str) -> list[str]:
    """Read file, strip lines, ignore empty lines."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.", file=sys.stderr)
        sys.exit(1)


def send_messages(api_keys: list[str],
                  messages: list[str],
                  numbers: list[str],
                  per_msg: int,
                  dry_run: bool = False) -> None:
    """
    Send each message to a chunk of numbers, rotating API keys every 500 messages.
    """
    url = "https://clawdtalk.com/v1/messages/send"
    total_numbers = len(numbers)
    keys_count = len(api_keys)

    key_index = 0          # current key index
    key_count = 0          # messages sent with current key
    send_count = 0         # total messages sent

    print(f"Starting: {len(messages)} message(s), {total_numbers} number(s), "
          f"{per_msg} numbers per message, {keys_count} API key(s).")

    for msg_idx, message in enumerate(messages):
        # Determine chunk for this message
        start = msg_idx * per_msg
        end = min(start + per_msg, total_numbers)
        if start >= total_numbers:
            print(f"No more numbers for message #{msg_idx+1} (ran out). Stopping.")
            break

        chunk = numbers[start:end]
        print(f"\n--- Sending message #{msg_idx+1} to numbers {start+1}-{end} "
              f"({len(chunk)} numbers) ---")

        for num_idx, number in enumerate(chunk, start=start+1):
            # Rotate key if needed
            if key_count >= 500:
                key_index += 1
                if key_index >= keys_count:
                    print(f"\nAll API keys exhausted (500 each). Sent {send_count} total.")
                    return
                key_count = 0
                print(f"Switched to API key #{key_index+1} (limit reset).")

            current_key = api_keys[key_index]
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json",
            }
            payload = {"to": number, "message": message}

            if dry_run:
                print(f"[DRY RUN] Would send to {number} with key #{key_index+1}")
                send_count += 1
                key_count += 1
                continue

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                status_code = response.status_code

                try:
                    resp_data = response.json()
                except json.JSONDecodeError:
                    resp_data = None

                if status_code == 200 and resp_data and resp_data.get("status") == "sent":
                    from_num = resp_data.get("from", "unknown")
                    msg_id = resp_data.get("id", "unknown")
                    print(f"[#{send_count+1}] ✅ {number} (msg {msg_idx+1}) -> SENT "
                          f"(key #{key_index+1}, from {from_num}, id: {msg_id})")
                else:
                    error_msg = "Unknown error"
                    if resp_data and "error" in resp_data:
                        err = resp_data["error"]
                        if isinstance(err, dict):
                            error_msg = err.get("message", str(err))
                        else:
                            error_msg = str(err)
                    elif resp_data and "message" in resp_data:
                        error_msg = resp_data["message"]
                    else:
                        error_msg = f"HTTP {status_code} - {response.text[:100]}"
                    print(f"[#{send_count+1}] ❌ {number} (msg {msg_idx+1}) -> FAILED: "
                          f"{error_msg} (key #{key_index+1})")

            except requests.exceptions.Timeout:
                print(f"[#{send_count+1}] ❌ {number} (msg {msg_idx+1}) -> TIMEOUT "
                      f"(key #{key_index+1})")
            except Exception as e:
                print(f"[#{send_count+1}] ❌ {number} (msg {msg_idx+1}) -> ERROR: {str(e)} "
                      f"(key #{key_index+1})")

            send_count += 1
            key_count += 1

        # Optional small delay between messages? Not required but could be added.
        # time.sleep(0.1)

    print(f"\nFinished. Total sends: {send_count}.")


def main():
    parser = argparse.ArgumentParser(
        description="Send SMS via Clawdtalk using files."
    )
    parser.add_argument(
        "--per-msg", type=int, default=250,
        help="Number of phone numbers to send per message (default: 250)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate sending without actually calling the API."
    )
    args = parser.parse_args()

    # Read files
    api_keys = read_lines("api_keys.txt")
    numbers = read_lines("numbers.txt")
    messages = read_lines("messages.txt")

    if not api_keys:
        print("Error: No API keys found in api_keys.txt", file=sys.stderr)
        sys.exit(1)
    if not numbers:
        print("Error: No numbers found in numbers.txt", file=sys.stderr)
        sys.exit(1)
    if not messages:
        print("Error: No messages found in messages.txt", file=sys.stderr)
        sys.exit(1)

    # Run sender
    send_messages(api_keys, messages, numbers, args.per_msg, args.dry_run)


if __name__ == "__main__":
    main()
