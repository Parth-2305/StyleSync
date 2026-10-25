# StyleSync hanger reader (ESP32 + RC522)

The reader sends the id of an RFID tag to the website each time a tagged hanger is held to it. The website does the thinking: it logs the garment as worn, groups pieces taken out together into a look, and notifies you.

## Parts

| Part | Notes |
|---|---|
| ESP32 development board (ESP32 DevKit V1 or similar) | Wi-Fi 2.4 GHz only |
| RC522 RFID reader module | Runs on **3.3 V** |
| RFID tags (13.56 MHz, MIFARE 1K cards or stickers) | One per hanger |
| 7 jumper wires, USB cable | |
| Optional: an LED on GPIO 2 (many boards already have one) | Blinks together with the buzzer (see below) |

## What the beeps mean

The website answers every scan, and the reader turns the answer into a sound (the LED blinks with it):

| Sound | Meaning |
|---|---|
| 1 short beep | Logged: the piece was counted as worn |
| 2 short beeps | New or unlinked tag: link it on the Hangers page |
| 1 long beep | You already wore this (or this outfit) this week: check the notification |
| 3 quick beeps | Something went wrong (Wi-Fi, wrong key, too many scans) |

Re-upload the sketch once to get these sounds. Your saved Wi-Fi settings stay in the ESP32's memory.

## Wiring

| RC522 pin | ESP32 pin |
|---|---|
| 3.3V | 3V3 |
| GND | GND |
| SDA (SS) | GPIO 5 |
| SCK | GPIO 18 |
| MOSI | GPIO 23 |
| MISO | GPIO 19 |
| RST | GPIO 22 |
| IRQ | not connected |

**Never connect the RC522 to 5 V.** It can be destroyed.

## Flashing

1. Install the Arduino IDE. In Boards Manager install **esp32 by Espressif Systems**. In Library Manager install **MFRC522 by GithubCommunity**.
2. Choose board **ESP32 Dev Module** and the right COM port.
3. Open `rfid_scanner/rfid_scanner.ino` and edit the four lines at the top: Wi-Fi name, Wi-Fi password, server address, device key.
4. Upload, then open the Serial Monitor at **115200** baud.

## Getting the device key

1. Log in to StyleSync, open **Hangers**, type a name and click **Pair a reader**.
2. Copy the key. It is shown **once**; the server stores only a hash.
3. Paste it into `DEVICE_KEY`. If you lose it, remove the reader on the Hangers page and pair a new one.

## Letting the ESP32 reach your computer

1. Both must be on the same Wi-Fi. Find your computer's address: run `ipconfig` and read the IPv4 address (for example 192.168.1.50).
2. Start the website so that it listens on the network, not only on your own computer:
   ```
   set HOST=0.0.0.0
   venv\Scripts\python.exe app.py
   ```
3. Allow Python through the Windows firewall when asked (private networks only).
4. Set `SERVER_URL` to `http://192.168.1.50:5000/api/iot/scan` (use your address).

Use this setup only on a network you trust. The built-in server is for development. A real deployment needs a proper web server with HTTPS (the key travels in a header, so plain HTTP over untrusted Wi-Fi would expose it).

## Changing the network later (college, phone hotspot) without uploading again

The Wi-Fi name, password, server address and key are saved inside the ESP32. To change them, open **Tools, Serial Monitor**, set it to **115200** baud and the line ending to **Newline**, then type one command per line and press Enter:

| Type this | What it does |
|---|---|
| `ssid My Hotspot` | Saves the Wi-Fi name |
| `pass mypassword` | Saves the Wi-Fi password |
| `url http://192.168.43.10:5000/api/iot/scan` | Saves your computer's address on THAT network |
| `key THE_KEY` | Saves a new device key (only if you paired a new reader) |
| `show` | Prints what is saved (secrets are hidden) |
| `restart` | Reboots the reader so it uses the new settings |

Your computer's address changes on every network, so after joining a new network run `ipconfig`, then type the new `url` line.

Tips for a demo: use your **phone's hotspot** (college Wi-Fi often stops devices talking to each other), make the hotspot **2.4 GHz** (Android: AP band 2.4 GHz; iPhone: Maximize Compatibility), and connect your laptop to the same hotspot. Windows may ask about the firewall again for the new network: allow Python.

## Using it

1. Hold a new tag to the reader. It appears under **Hangers, step 2** as a waiting tag. Choose the garment and click **Link**.
2. From now on, holding that hanger's tag to the reader logs the garment as worn and sends a notification.
3. Pieces scanned within 2 hours of each other appear together as one "Hanger look" in History.
4. **The one-week rule.** If you tap any piece (clothes, shoes or accessories) that you wore in the last 7 days, the notification says so ("Black T-Shirt detected. You wore it yesterday. Repeat it, or try Grey Shirt or Blue Shirt instead?"). If the pieces you take out include every piece of a look from earlier this week, it warns about the whole outfit. The Outfit Matcher follows the same rule.
5. To see the warning without waiting a day: `python tools/pretend_worn.py --email YOUR_EMAIL --piece "T-Shirt" --days 1`, then tap that piece's tag.

## Testing without hardware

- On the Hangers page, step 4: **Simulate scan**.
- Or from the command line, like a real reader would:
  ```
  venv\Scripts\python.exe tools\fake_reader.py --key YOUR_KEY --tag 04A1B2C3
  ```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Serial Monitor shows version `0x00` or `0xFF` | Wiring problem: check 3.3 V, GND and the SPI wires |
| "Wi-Fi failed" | Use a 2.4 GHz network; check name and password |
| Code `-1` or a timeout when sending | The computer is not reachable: wrong address, `HOST=0.0.0.0` not set, or the firewall |
| Code `401` | Wrong key, or the reader was removed on the Hangers page |
| Code `429` | Too many scans in a minute (limit: 30 per reader) |
| Status `ignored` | The same tag was scanned within 5 seconds |

## Security notes

- The key can do one thing: report scans for its owner. It cannot read your wardrobe or log in.
- Tag ids are not secret and can be copied by anyone who holds a tag near a phone with an NFC app. Treat a scan as a convenience for logging, not as proof of identity.
- Do not commit the sketch with your real Wi-Fi password or key filled in.
