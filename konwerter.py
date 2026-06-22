import numpy as np
from scipy.datasets import electrocardiogram

# 1. Pobranie oficjalnego, prawdziwego sygnału EKG z bazy PhysioNet (częstotliwość 360 Hz)
ecg_signal = electrocardiogram()

# 2. Wycinamy jedno idealne, pełne uderzenie serca (około 200-250 próbek)
# Indeksy od 300 do 550 zawierają wzorcowy, czysty zespół QRS, załamek P i T
START_INDEX = 300
END_INDEX = 550
raw_data = ecg_signal[START_INDEX:END_INDEX]

# 3. Skalowanie matematyczne do zakresu Twojego 12-bitowego DAC (0 - 4095)
min_val = min(raw_data)
max_val = max(raw_data)

scaled_data = []
for val in raw_data:
    # Normalizacja do zakresu 0.0 - 1.0
    normalized = (val - min_val) / (max_val - min_val)
    # Przeskalowanie na zakres DAC (0-4095)
    dac_val = int(normalized * 4095)
    scaled_data.append(dac_val)

# 4. Wygenerowanie gotowej tablicy C++ dla ESP32
print(f"\n// Wygenerowano automatycznie. Liczba probek: {len(scaled_data)}")
print(f"const uint16_t ecgRealNormal[{len(scaled_data)}] PROGMEM = {{")

# Formatowanie po 12 wartości w linii, żeby ładnie wyglądało w Arduino IDE
for i in range(0, len(scaled_data), 12):
    chunk = scaled_data[i:i+12]
    line = "  " + ", ".join(str(x) for x in chunk)
    if i + 12 < len(scaled_data):
        line += ","
    print(line)
    
print("};")
print(f"const int ecgLength = {len(scaled_data)};")
print("\n# Kopiuj powyzszy blok i wklej do Arduino IDE w miejsce starej tablicy!")