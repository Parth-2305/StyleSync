# StyleSync: how to start everything (demo checklist)

Follow the steps in order, every time. About 10 minutes the first time, 3 minutes once you know it.
Commands are for Windows PowerShell inside VS Code (Terminal -> New Terminal).

---

## Step 0. The day before (and the morning of) a demo

1. Open https://supabase.com, log in, open the StyleSync project.
2. If it says **Paused**, click **Restore / Resume**. Wait 3 to 5 minutes until it says **Active**. (Free projects pause after about a week without use.)
3. Open your own website once and log in. This keeps it awake.

## Step 1. Choose the Wi-Fi (the laptop AND the ESP32 must be on the SAME one)

- At home: your home Wi-Fi.
- At college: turn on your **phone hotspot** and set it to **2.4 GHz** (the ESP32 cannot use 5 GHz).
- Connect the **laptop** to that Wi-Fi.

## Step 2. Find the laptop's address

```powershell
ipconfig
```

Look under your Wi-Fi adapter for **IPv4 Address**, for example `192.168.43.10`. Write it down. It changes on every network.

## Step 3. Start the website

In the VS Code terminal, in the project folder:

```powershell
$env:HOST="0.0.0.0"; venv\Scripts\python.exe app.py
```

- You should see `Running on http://127.0.0.1:5000`. Leave this terminal open (closing it stops the site).
- If Windows asks about the firewall, click **Allow** (private networks). Without this the ESP32 cannot reach the laptop.
- If you see "Startup blocked", the `.env` file is missing or wrong.
- Open Chrome at **http://127.0.0.1:5000** and log in.

## Step 4. Plug in and set up the ESP32

1. Connect the ESP32 to the laptop with the USB cable.
2. Open the **Arduino IDE**. Choose **Tools -> Port** and select the ESP32's COM port.
3. Open **Tools -> Serial Monitor**. Set the bottom-right boxes to **115200 baud** and **Newline**.
4. Press the small **EN** button on the ESP32 once so the messages appear.
5. Type `show` and press Enter. Check `ssid` and `url` match THIS network and THIS laptop address.
6. If anything is different, type these (one per line, Enter after each), using your real values:

```
ssid MyHotspotName
pass MyHotspotPassword
url http://192.168.43.10:5000/api/iot/scan
restart
```

7. After the restart, wait for: `Connected. Reader address: ...` and **2 short beeps/blinks**. That means Wi-Fi works.
8. `Wi-Fi failed`? Check the name and password, and that the network is 2.4 GHz.

(After this step you may close the Serial Monitor. The ESP32 only needs power: USB from the laptop or a power bank.)

## Step 5. Check the reader on the website

1. In Chrome open **Hangers**. A reader should be listed under "Your readers".
2. If the reader's key is lost, or you are using a different account:
   - Type a name, click **Pair a reader**, copy the key (shown only once).
   - In the Serial Monitor type: `key PASTE_THE_KEY` then `restart`.
3. Remember: **one reader belongs to one account** (whoever paired it). Log in with that account.

## Step 6. Turn on browser pop-ups (once per browser)

Click the bell at the top right -> **Turn on browser notifications** -> **Allow**.

## Step 7. Test before showing anyone

1. Keep the **Hangers** page open (green **Live** badge).
2. Touch a **linked** card to the reader: **1 short beep**, and within about 3 seconds the page updates and a pop-up appears.
3. Touch a **new** card: **2 short beeps**, it appears under "Link tags". Link it to a piece.

| Beeps | Meaning |
|---|---|
| 1 short | Logged as worn |
| 2 short | New or unlinked tag |
| 1 long | Already worn this week |
| 3 quick | Error (Wi-Fi, key, too many scans) |

## Step 8. Demo script (3 minutes)

1. Wardrobe: show the pieces, the green "Hanger tag assigned" dot and "Worn N times".
2. Outfit Matcher: Party + All-season -> show the match percentage and the reasons -> Shuffle.
3. Hangers page: scan a card live, show the beep and the page updating by itself.
4. Repeat warning: in a second terminal run
   `venv\Scripts\python.exe tools\pretend_worn.py --email YOU@EMAIL --piece "Shoes" --days 1`
   then scan that piece again: **long beep** and the warning with alternatives.
5. History: show the "Hanger look".
6. If the hardware misbehaves, use **Simulate scan** on the Hangers page. It runs the same code.

## Step 9. Shutting down

- Click in the VS Code terminal and press `Ctrl + C` to stop the website.
- Unplug the ESP32.

---

## If something goes wrong

| What you see | Do this |
|---|---|
| Site shows an error right after a long break | Supabase is paused or still waking up (Step 0). Wait 3 to 5 minutes, refresh |
| ESP32 says "Wi-Fi failed" | Wrong name or password, or a 5 GHz network. Use `ssid`, `pass`, `restart` |
| ESP32 connects but 3 quick beeps | `show`: is the `url` the CURRENT laptop address (Step 2)? Is the site running with HOST 0.0.0.0? Firewall allowed? Wrong key (3 quick beeps and "401" in Serial Monitor)? Pair again and use `key` |
| Beep OK but nothing on the site | You are logged in to a different account than the one that paired the reader |
| Serial Monitor is empty | Press EN, check 115200 baud, check the right COM port |
| No browser pop-ups | Bell -> Turn on browser notifications; allow notifications for the site in Chrome settings |
| Pop-up shows but the bell does not change | Wait up to 15 seconds or refresh |
| "Startup blocked" in the terminal | `.env` is missing or has a placeholder value |
| `venv\Scripts\python.exe` not found | In the project folder run `python -m venv venv` then `venv\Scripts\pip install -r requirements.txt` |

More detail: `PROJECT_LOG.md` (how it works), `../firmware/README.md` (wiring), `HANDOFF_FOR_REPORT.md`.
