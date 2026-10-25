/*
  StyleSync hanger reader: ESP32 + RC522 RFID module (+ optional buzzer).

  What it does: when you hold a tag (on a hanger) to the reader, it reads the tag's id and sends it over Wi-Fi to the
  StyleSync website. The website decides what that means (log the piece as worn, or remember a new tag).
  The reader sends ONLY the tag id and its secret key; it never says which user it belongs to (the key decides that).

  CHANGING NETWORKS (home, phone hotspot, college): you do NOT need to upload the code again.
  Open Tools -> Serial Monitor (115200 baud, line ending "Newline"), type a command and press Enter:
      ssid My Hotspot Name          (the Wi-Fi name)
      pass mypassword               (the Wi-Fi password)
      url http://192.168.43.10:5000/api/iot/scan     (your computer's address on THAT network)
      key PASTE_THE_DEVICE_KEY      (only if you paired a new reader)
      scan                          (lists the Wi-Fi networks the ESP32 can see, numbered)
      use 2                         (picks network number 2 from the scan as the Wi-Fi name)
      show                          (prints the saved settings, hiding secrets)
      restart                       (reboot so the new settings are used)
  The settings are saved inside the ESP32 and survive power-off.

  Wiring (ESP32 DevKit  ->  RC522):   3.3V -> 3.3V   GND -> GND   GPIO5 -> SDA(SS)   GPIO18 -> SCK
                                      GPIO23 -> MOSI   GPIO19 -> MISO   GPIO22 -> RST   (IRQ is not connected)
  Buzzer: GPIO25 -> buzzer (+), GND -> buzzer (-).
  IMPORTANT: the RC522 runs on 3.3V. Connecting it to 5V can destroy it.

  What the buzzer tells you (the website's answer decides):
      1 short beep  = logged: the piece was counted as worn
      2 short beeps = new or unlinked tag: link it on the Hangers page
      1 long beep   = you already wore this (or this outfit) this week: check the notification
      3 quick beeps = something went wrong (Wi-Fi, wrong key, too many scans)

  Libraries (Arduino IDE -> Library Manager): "MFRC522" by GithubCommunity. Board: "ESP32 Dev Module" (Espressif ESP32 package).
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>

// ============ FIRST-TIME SETTINGS (used until you save your own with the Serial commands above) ============
const char* DEFAULT_SSID = "YOUR_WIFI_NAME";                              // a 2.4 GHz network (the ESP32 cannot use 5 GHz)
const char* DEFAULT_PASS = "YOUR_WIFI_PASSWORD";
const char* DEFAULT_URL  = "http://192.168.1.50:5000/api/iot/scan";       // your computer's address (run ipconfig), port 5000
const char* DEFAULT_KEY  = "PASTE_THE_KEY_FROM_THE_HANGERS_PAGE";         // shown once when you pair a reader
// ===========================================================================================================

const uint8_t SS_PIN = 5, RST_PIN = 22;
const uint8_t LED_PIN = 2;                       // the small blue LED on most ESP32 boards
const int8_t BUZZER_PIN = 25;                    // your buzzer is on GPIO 25 (use -1 if you ever remove it)
const unsigned long SAME_TAG_PAUSE_MS = 4000;    // ignore the same tag for 4 s, so one swipe is sent once

MFRC522 rfid(SS_PIN, RST_PIN);
Preferences prefs;                               // the ESP32's small permanent memory
String wifiSsid, wifiPass, serverUrl, deviceKey;
String typedLine;                                // what you are typing in the Serial Monitor
String lastUid;
unsigned long lastSentAt = 0;

// ---------------------------------------------------------------- saved settings
void loadSettings() {
  prefs.begin("stylesync", true);
  wifiSsid  = prefs.getString("ssid", DEFAULT_SSID);
  wifiPass  = prefs.getString("pass", DEFAULT_PASS);
  serverUrl = prefs.getString("url",  DEFAULT_URL);
  deviceKey = prefs.getString("key",  DEFAULT_KEY);
  prefs.end();
}

void saveSetting(const char* name, const String& value) {
  prefs.begin("stylesync", false);
  prefs.putString(name, value);
  prefs.end();
}

String hide(const String& secret) {              // show only the first 3 characters of a secret
  return secret.length() > 3 ? secret.substring(0, 3) + "..." : secret;
}

void showSettings() {
  Serial.println("---- saved settings ----");
  Serial.println("ssid: " + wifiSsid);
  Serial.println("pass: " + hide(wifiPass));
  Serial.println("url : " + serverUrl);
  Serial.println("key : " + hide(deviceKey));
  Serial.println("------------------------");
}

// Lists the Wi-Fi networks the ESP32 can really see. `use 2` then picks number 2, so odd names (spaces, hidden characters) always work.
String scannedNames[20];
int scannedCount = 0;

void scanNetworks() {
  Serial.println("Scanning for Wi-Fi networks (about 5 seconds)...");
  WiFi.disconnect(true);                         // stop the failed connection attempt first
  delay(300);
  WiFi.mode(WIFI_STA);
  int found = WiFi.scanNetworks();
  scannedCount = 0;
  if (found <= 0) { Serial.println("No networks found. Is the hotspot on, and set to 2.4 GHz?"); return; }
  for (int i = 0; i < found && scannedCount < 20; i++) {
    scannedNames[scannedCount] = WiFi.SSID(i);
    Serial.printf("%2d. \"%s\"  (%d characters, signal %d dBm, channel %d)\n", scannedCount + 1, scannedNames[scannedCount].c_str(),
                  (int)scannedNames[scannedCount].length(), WiFi.RSSI(i), WiFi.channel(i));
    scannedCount++;
  }
  Serial.println("Type  use <number>  to pick one (example: use 2), then  pass <password>  and  restart.");
}

void runCommand(String line) {
  line.trim();
  if (line.length() == 0) return;
  int space = line.indexOf(' ');
  String command = space < 0 ? line : line.substring(0, space);
  String value = space < 0 ? "" : line.substring(space + 1);
  value.trim();
  command.toLowerCase();

  if (command == "ssid" && value.length() > 0)                { wifiSsid = value;  saveSetting("ssid", value);  Serial.println("Saved the Wi-Fi name. Type restart to use it."); }
  else if (command == "pass")                                 { wifiPass = value;  saveSetting("pass", value);  Serial.println("Saved the Wi-Fi password. Type restart to use it."); }
  else if (command == "url" && value.startsWith("http"))      { serverUrl = value; saveSetting("url", value);   Serial.println("Saved the server address."); }
  else if (command == "key" && value.length() >= 32)          { deviceKey = value; saveSetting("key", value);   Serial.println("Saved the device key."); }
  else if (command == "scan")                                 { scanNetworks(); }
  else if (command == "use" && value.toInt() >= 1 && value.toInt() <= scannedCount) { wifiSsid = scannedNames[value.toInt() - 1]; saveSetting("ssid", wifiSsid); Serial.println("Saved Wi-Fi name: " + wifiSsid + ". Now type pass <password>, then restart."); }
  else if (command == "show")                                 { showSettings(); }
  else if (command == "restart")                              { Serial.println("Restarting..."); delay(300); ESP.restart(); }
  else Serial.println("Commands: ssid <name> | pass <password> | url <address> | key <key> | scan | use <number> | show | restart");
}

// Collects what you type; runs the command when you press Enter.
void handleSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { typedLine += c; continue; }
    runCommand(typedLine);
    typedLine = "";
  }
}

// ---------------------------------------------------------------- feedback
// One short blink + beep = sent OK. Three quick ones = something went wrong.
void blink(int times, int ms = 120) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    if (BUZZER_PIN >= 0) digitalWrite(BUZZER_PIN, HIGH);   // an "active" buzzer sounds whenever its pin is HIGH
    delay(ms);
    digitalWrite(LED_PIN, LOW);
    if (BUZZER_PIN >= 0) digitalWrite(BUZZER_PIN, LOW);
    delay(ms);
  }
}

// ---------------------------------------------------------------- Wi-Fi and sending
void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  Serial.print("Connecting to Wi-Fi \"" + wifiSsid + "\"");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) { delay(400); Serial.print("."); handleSerialInput(); }
  if (WiFi.status() == WL_CONNECTED) {
    WiFi.setSleep(false);                          // no Wi-Fi power saving: a phone hotspot otherwise drops the first request after a quiet moment
    Serial.printf("\nConnected. Reader address: %s\n", WiFi.localIP().toString().c_str());
    blink(2);
  } else {
    Serial.println("\nWi-Fi failed. Check the name and password (2.4 GHz only). You can change them: type ssid ..., pass ..., then restart.");
  }
}

// A tag id as hex text, e.g. {0x04,0xA1,0xB2,0xC3} -> "04A1B2C3".
String uidToHex(const MFRC522::Uid& uid) {
  String hex;
  char part[3];
  for (byte i = 0; i < uid.size; i++) {
    snprintf(part, sizeof(part), "%02X", uid.uidByte[i]);
    hex += part;
  }
  return hex;
}

// Returns the HTTP status: 200 = the website accepted it, 401 = wrong or removed key, 429 = too many scans.
int sendScan(const String& uid, String& reply) {
  HTTPClient http;
  http.setTimeout(6000);
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", deviceKey);
  int code = http.POST("{\"tag_uid\":\"" + uid + "\"}");
  if (code > 0) { reply = http.getString(); Serial.println(reply); }   // for example {"repeat":false,"status":"logged"}
  http.end();
  return code;
}

// ---------------------------------------------------------------- main program
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  if (BUZZER_PIN >= 0) pinMode(BUZZER_PIN, OUTPUT);
  SPI.begin(18, 19, 23, SS_PIN);                    // SCK, MISO, MOSI, SS
  rfid.PCD_Init();
  delay(50);
  loadSettings();
  Serial.println("\n=== StyleSync reader ===");
  byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  Serial.printf("RC522 version: 0x%02X (0x91 or 0x92 is normal; 0x00 or 0xFF means a wiring problem)\n", version);
  showSettings();
  Serial.println("Type 'show' to see settings, or ssid / pass / url / key to change them.");
  connectWifi();
}

void loop() {
  handleSerialInput();
  if (WiFi.status() != WL_CONNECTED) { connectWifi(); delay(1000); return; }
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;   // nothing held to the reader

  String uid = uidToHex(rfid.uid);
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  if (uid == lastUid && millis() - lastSentAt < SAME_TAG_PAUSE_MS) return;

  lastUid = uid;
  lastSentAt = millis();
  Serial.println("Tag: " + uid);
  String reply;
  int code = sendScan(uid, reply);
  if (code <= 0) {                                   // could not connect: try once more straight away before the error beeps
    Serial.println("First try failed, trying again...");
    delay(300);
    code = sendScan(uid, reply);
  }
  if (code == 200) {
    reply.replace(" ", "");                                  // the website may or may not put spaces in its JSON
    if (reply.indexOf("\"status\":\"unknown\"") >= 0)  blink(2, 150);   // new tag: two short beeps
    else if (reply.indexOf("\"repeat\":true") >= 0)     blink(1, 900);   // worn this week: one long beep
    else                                                  blink(1, 200);   // logged: one short beep
  } else {
    Serial.printf("Could not send (code %d)\n", code);
    blink(3, 100);
  }
}
