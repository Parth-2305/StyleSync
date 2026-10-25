"""A pretend ESP32: sends a scan to the website exactly like the real reader does. Use it to test without hardware.

    venv\\Scripts\\python.exe tools\\fake_reader.py --key YOUR_DEVICE_KEY --tag 04A1B2C3
    venv\\Scripts\\python.exe tools\\fake_reader.py --key YOUR_DEVICE_KEY --tag 04A1B2C3 --url http://192.168.1.50:5000/api/iot/scan
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description="Send one RFID scan to StyleSync.")
parser.add_argument("--key", required=True, help="the device key shown when you paired the reader")
parser.add_argument("--tag", required=True, help="a tag id in hex, for example 04A1B2C3")
parser.add_argument("--url", default="http://127.0.0.1:5000/api/iot/scan")
args = parser.parse_args()

if not args.url.startswith(("http://", "https://")):  # only web addresses, never file: or anything else
    sys.exit("The address must start with http:// or https://")

request = urllib.request.Request(
    args.url,
    data=json.dumps({"tag_uid": args.tag}).encode("utf-8"),
    headers={"Content-Type": "application/json", "X-Device-Key": args.key},  # the same two things the ESP32 sends
)
try:
    with urllib.request.urlopen(request, timeout=8) as response:  # nosec B310: scheme checked above
        print(response.status, response.read().decode())
except urllib.error.HTTPError as error:
    print(error.code, error.read().decode())
    sys.exit(1)
except urllib.error.URLError as error:
    print("Could not reach the server:", error.reason)
    sys.exit(1)
