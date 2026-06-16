#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_MCP4725.h>

// --- KONFIGURACJA SIECI ---
const char* ssid = "XXX";
const char* password = "XXX";
const char* mqtt_server = "X.X.X.X";

WiFiClient espClient;
PubSubClient client(espClient);

// --- OBIEKTY SPRZĘTOWE ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
Adafruit_MCP4725 dac;
#define LED_PIN D0 

// --- DANE EKG ---
// Symulacja przebiegu EKG dla 12-bitowego przetwornika (wartości od 0 do 4095)
// Wartość 2048 to nasza linia izoelektryczna (połowa napięcia 3.3V, czyli ok. 1.65V)
const uint16_t ecgWave[] = {
  2048, 2048, 2048, 2048, 2150, 2250, 2150, 2048, // Załamek P (przedsionki)
  2048, 1900, 3800, 1000, 2048, 2048, 2048,       // Zespół QRS (skurcz komór)
  2048, 2048, 2100, 2300, 2400, 2300, 2100, 2048, // Załamek T
  2048, 2048, 2048, 2048, 2048, 2048, 2048, 2048  // Faza spoczynku
};
const int ecgLength = sizeof(ecgWave) / sizeof(ecgWave[0]);
int currentBpm = 60; // Domyślne tętno startowe

void updateDisplay(String status, String bpm) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 10);
  display.println(status);
  display.setCursor(0, 30);
  display.println("Tetno: " + bpm + " BPM");
  display.display();
}

void setup_wifi() {
  updateDisplay("Laczenie z Wi-Fi:", String(ssid));
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  updateDisplay("Polaczono! IP:", WiFi.localIP().toString());
  delay(2000);
}

void reconnect() {
  while (!client.connected()) {
    updateDisplay("MQTT Broker:", "Laczem sie...");
    if (client.connect("ESP32_Generator_EKG")) {
      updateDisplay("MQTT Broker:", "POLACZONO!");
      client.publish("projekt_ekg/status", "Symulator EKG zglasza gotowosc!");
      delay(1000);
    } else {
      updateDisplay("Blad MQTT!", "Ponawiam za 5s...");
      delay(5000);
    }
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  
  // Inicjalizacja ekranu (0x3C)
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Blad OLED"));
    for(;;);
  }
  
  // Inicjalizacja DAC (0x60)
  if (!dac.begin(0x60)) {
    updateDisplay("BLAD SPRZETOWY!", "Nie wykryto DAC!");
    for(;;);
  }

  updateDisplay("GENERATOR EKG", "Inicjalizacja...");
  delay(2000);

  setup_wifi();
  client.setServer(mqtt_server, 1883);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Wypuszczanie fali EKG na przetwornik DAC
  for (int i = 0; i < ecgLength; i++) {
    // Wysyłamy napięcie do układu scalonego
    dac.setVoltage(ecgWave[i], false);
    
    // Niewielkie opóźnienie kształtujące płynność fali
    delay(15); 
  }
  
  // Po każdym pełnym "uderzeniu" serca aktualizujemy resztę systemów
  digitalWrite(LED_PIN, HIGH);
  String bpmStr = String(currentBpm);
  
  // Publikacja na kanał MQTT
  client.publish("projekt_ekg/tento", bpmStr.c_str());
  
  // Aktualizacja ekranu
  updateDisplay("NADAWANIE EKG...", bpmStr);
  
  digitalWrite(LED_PIN, LOW);
  
  // Przerwa między uderzeniami symulująca rytm 60 uderzeń na minutę
  delay(400); 
}