"""
Konwerter EKG z PhysioNet -> tablice C++ dla ESP32 (12-bit DAC, 0-4095).

Co robi:
  - laczy sie z physionet.org przez biblioteke wfdb (POTRZEBNY INTERNET),
  - dla kazdej jednostki chorobowej PRZESZUKUJE prawdziwe bazy danych po
    adnotacjach rytmu i wycina pierwszy pasujacy fragment sygnalu,
  - przeprobkowuje fragment do 128 probek i skaluje do zakresu DAC (0-4095),
  - wypisuje gotowe tablice C++ do wklejenia w kod ESP32.

INSTALACJA:
    pip install wfdb numpy scipy

URUCHOMIENIE (zapis do pliku):
    python konwerter_physionet.py > tablice.txt

Postep leci na stderr, wiec w tablice.txt zostaje czysty kod C++.
"""

import sys
import numpy as np
from scipy.signal import resample

try:
    import wfdb
except ImportError:
    sys.exit("Brak biblioteki wfdb. Uruchom: pip install wfdb numpy scipy")

OUT_LEN = 128
DAC_MAX = 4095
LINE_ISO = 2048


def log(msg):
    print(msg, file=sys.stderr)


def scale_to_dac(seg):
    seg = np.asarray(seg, dtype=float)
    seg = seg[~np.isnan(seg)]
    if len(seg) < 8:
        return [LINE_ISO] * OUT_LEN
    seg = resample(seg, OUT_LEN)
    lo, hi = seg.min(), seg.max()
    if hi - lo < 1e-6:
        return [LINE_ISO] * OUT_LEN
    norm = (seg - lo) / (hi - lo)
    return [int(round(v * DAC_MAX)) for v in norm]


def emit_c_array(name, values, comment):
    print(f"\n// {comment}")
    print(f"const uint16_t {name}[{len(values)}] PROGMEM = {{")
    for i in range(0, len(values), 16):
        chunk = values[i:i + 16]
        line = "  " + ", ".join(str(x) for x in chunk)
        if i + 16 < len(values):
            line += ","
        print(line)
    print("};")


def grab_rhythm(db, records, labels, win_sec=1.4, pre_sec=0.1, channel=0):
    for rec in records:
        try:
            log(f"  ... probuje {db}/{rec}")
            r = wfdb.rdrecord(rec, pn_dir=db)
            ann = wfdb.rdann(rec, "atr", pn_dir=db)
            fs = r.fs
            sig = r.p_signal[:, channel]
            win = int(win_sec * fs)
            pre = int(pre_sec * fs)
            for i, note in enumerate(ann.aux_note):
                lab = note.strip().strip("\x00")
                if lab in labels:
                    start = max(0, ann.sample[i] - pre)
                    seg = sig[start:start + win]
                    if len(seg) >= win * 0.8:
                        return seg, f"PhysioNet {db}/{rec}  rytm {lab}  (fs={fs}Hz)"
        except Exception as e:
            log(f"      blad {db}/{rec}: {e}")
    return None, None


def grab_normal(db, records, win_sec=1.4, channel=0):
    for rec in records:
        try:
            log(f"  ... probuje {db}/{rec}")
            r = wfdb.rdrecord(rec, pn_dir=db)
            ann = wfdb.rdann(rec, "atr", pn_dir=db)
            fs = r.fs
            sig = r.p_signal[:, channel]
            win = int(win_sec * fs)
            beats = [s for s, sym in zip(ann.sample, ann.symbol) if sym == "N"]
            if len(beats) > 20:
                center = beats[len(beats) // 2]
                start = max(0, center - int(0.25 * fs))
                seg = sig[start:start + win]
                if len(seg) >= win * 0.8:
                    return seg, f"PhysioNet {db}/{rec}  rytm zatokowy  (fs={fs}Hz)"
        except Exception as e:
            log(f"      blad {db}/{rec}: {e}")
    return None, None


NSRDB = ["16265", "16272", "16273", "16420", "16483", "16539", "16773"]
VFDB  = ["418", "419", "420", "421", "422", "423", "424", "425",
         "426", "427", "428", "429", "430", "602", "605", "607",
         "609", "610", "611", "612", "614", "615"]
AFDB  = ["08405", "08378", "08434", "08455", "07910", "07879", "06995",
         "05091", "04936", "04746", "04126", "04048", "04043", "04015"]


def main():
    log("=== Konwerter PhysioNet -> ESP32 ===")
    log("Laczenie z physionet.org (moze chwile potrwac)...\n")

    jobs = [
        ("ecgRealNormal", grab_normal, ["nsrdb", NSRDB],
         "NORMALNY (rytm zatokowy)"),
        ("ecgTachy", grab_rhythm, ["vfdb", VFDB, {"(VT"}],
         "V-TACH (czestoskurcz komorowy)"),
        ("ecgVfib", grab_rhythm, ["vfdb", VFDB, {"(VF", "(VFL"}],
         "V-FIB (migotanie/trzepotanie komor)"),
        ("ecgFlutter", grab_rhythm, ["afdb", AFDB, {"(AFL"}],
         "TRZEPOTANIE PRZEDSIONKOW"),
        ("ecgAsystole", grab_rhythm, ["vfdb", VFDB, {"(ASYS"}],
         "ASYSTOLIA (brak czynnosci elektr.)"),
    ]

    found, missing = [], []
    for name, getter, args, desc in jobs:
        log(f"[{name}] {desc}")
        seg, src = getter(*args)
        if seg is not None:
            emit_c_array(name, scale_to_dac(seg), f"{desc} -- {src}")
            found.append((name, src))
            log(f"  OK: {src}\n")
        else:
            missing.append((name, desc))
            log("  NIE ZNALEZIONO w przeszukanych rekordach\n")

    print("\n// ============================================================")
    print("// STEMI i BLOK AV:")
    print("// To NIE sa zaburzenia rytmu tylko morfologii / przewodzenia.")
    print("// Nie wystepuja jako czyste petle w bazach rytmicznych powyzej.")
    print("// Realne zrodlo: STEMI -> PTB Diagnostic ECG Database (ptbdb),")
    print("// rekordy z rozpoznaniem 'Myocardial infarction'. Blok AV ->")
    print("// pojedyncze rekordy mitdb z wypadaniem zespolow QRS.")
    print("// Zostaw swoje dotychczasowe ecgStemi[] i ecgAvBlock[] -")
    print("// sa syntetyczne, ale poprawne ksztaltem.")
    print("// ============================================================")

    log("\n=== PODSUMOWANIE ===")
    for n, s in found:
        log(f"  [OK]   {n:14s} <- {s}")
    for n, d in missing:
        log(f"  [BRAK] {n:14s} ({d})")
    log("\nSkopiuj tablice z pliku tablice.txt do kodu ESP32.")


if __name__ == "__main__":
    main()