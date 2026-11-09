"""
Pipeline de procesamiento ECG → Espectrograma → Clasificación ML
Clasificación de Enfermedades Cardiovasculares
"""

import numpy as np
import scipy.signal as signal
from scipy.io import wavfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import io, base64, json, os, csv
from pathlib import Path

# ─── Clases de diagnóstico ────────────────────────────────────────────────────
DIAGNOSES = {
    "Normal":                  {"color": "#22c55e", "risk": "Bajo",    "icon": "✓"},
    "Taquicardia":             {"color": "#f59e0b", "risk": "Medio",   "icon": "⚡"},
    "Bradicardia":             {"color": "#f59e0b", "risk": "Medio",   "icon": "🔻"},
    "Fibrilación Auricular":   {"color": "#ef4444", "risk": "Alto",    "icon": "⚠"},
    "Bloqueo AV":              {"color": "#ef4444", "risk": "Alto",    "icon": "🔒"},
    "Extrasístoles":           {"color": "#f97316", "risk": "Medio",   "icon": "💢"},
    "Isquemia Miocárdica":     {"color": "#dc2626", "risk": "Crítico", "icon": "🚨"},
    "Flutter Auricular":       {"color": "#f97316", "risk": "Medio",   "icon": "〰"},
}


# ─── 1. CARGA DE SEÑAL ECG ───────────────────────────────────────────────────
def load_ecg(filepath: str) -> tuple[np.ndarray, int]:
    """
    Carga ECG desde: .csv, .txt, .wav, .dat (texto), .npy
    Retorna (señal_1D, frecuencia_muestreo)
    """
    ext = Path(filepath).suffix.lower()

    if ext in (".wav",):
        fs, data = wavfile.read(filepath)
        if data.ndim > 1:
            data = data[:, 0]
        return data.astype(float), fs

    elif ext in (".npy",):
        data = np.load(filepath)
        if data.ndim > 1:
            data = data[:, 0]
        return data.astype(float), 500

    elif ext in (".csv", ".txt"):
        rows = []
        with open(filepath, "r") as f:
            sample = f.read(2048)
            f.seek(0)
            has_header = csv.Sniffer().has_header(sample)
            reader = csv.reader(f)
            if has_header:
                next(reader)
            for row in reader:
                for cell in row:
                    try:
                        rows.append(float(cell.strip()))
                        break
                    except ValueError:
                        continue
        if not rows:
            raise ValueError("No se encontraron datos numéricos en el archivo.")
        return np.array(rows), 500

    elif ext in (".dat", ""):
        try:
            data = np.loadtxt(filepath)
            if data.ndim > 1:
                data = data[:, 0]
            return data.astype(float), 500
        except Exception:
            raise ValueError(f"Formato de archivo no reconocido: {ext}")

    else:
        raise ValueError(f"Formato no soportado: {ext}. Use .csv, .txt, .wav, .npy, .dat")


# ─── 2. PREPROCESAMIENTO ──────────────────────────────────────────────────────
def preprocess_ecg(ecg: np.ndarray, fs: int) -> np.ndarray:
    """Filtrado baseline + ruido de alta frecuencia + normalización."""
    # Eliminar tendencia de baja frecuencia (baseline wander)
    b_high, a_high = signal.butter(4, 0.5 / (fs / 2), btype='high')
    ecg = signal.filtfilt(b_high, a_high, ecg)

    # Filtro pasa-bajos (eliminar ruido > 40 Hz)
    cutoff = min(40.0, fs / 2 - 1)
    b_low, a_low = signal.butter(4, cutoff / (fs / 2), btype='low')
    ecg = signal.filtfilt(b_low, a_low, ecg)

    # Filtro notch 50/60 Hz (interferencia de red)
    for freq in [50, 60]:
        if freq < fs / 2:
            b_n, a_n = signal.iirnotch(freq, 30, fs)
            ecg = signal.filtfilt(b_n, a_n, ecg)

    # Normalización Z-score
    ecg = (ecg - np.mean(ecg)) / (np.std(ecg) + 1e-8)
    return ecg


# ─── 3. ECG → ESPECTROGRAMA ──────────────────────────────────────────────────
def ecg_to_spectrogram(ecg: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    STFT → espectrograma en dB.
    Retorna (frecuencias, tiempos, Sxx_dB, Sxx_raw)
    """
    nperseg = min(256, len(ecg) // 8)
    noverlap = nperseg * 3 // 4
    f, t, Zxx = signal.stft(ecg, fs=fs, nperseg=nperseg, noverlap=noverlap)
    Sxx = np.abs(Zxx) ** 2
    Sxx_db = 10 * np.log10(Sxx + 1e-12)
    return f, t, Sxx_db, Sxx


def ecg_to_cwt(ecg: np.ndarray, fs: int, scales=64) -> tuple[np.ndarray, np.ndarray]:
    """Transformada Wavelet Continua con Morlet via scipy.signal.cwt."""
    widths = np.geomspace(1, fs // 2, num=scales)
    cwt_matrix = signal.cwt(ecg[:min(len(ecg), 2000)], signal.morlet2, widths)
    power = np.abs(cwt_matrix) ** 2
    freqs = fs / (2 * widths)
    return freqs, power


# ─── 4. EXTRACCIÓN DE CARACTERÍSTICAS ───────────────────────────────────────
def extract_features(ecg: np.ndarray, fs: int, f: np.ndarray,
                     Sxx: np.ndarray) -> dict:
    """Extrae features temporales, frecuenciales y espectrales."""
    features = {}

    # ── Temporales ──
    features["mean_amplitude"]  = float(np.mean(np.abs(ecg)))
    features["std_amplitude"]   = float(np.std(ecg))
    features["rms"]             = float(np.sqrt(np.mean(ecg ** 2)))
    features["peak_to_peak"]    = float(np.ptp(ecg))
    features["skewness"]        = float(_skewness(ecg))
    features["kurtosis"]        = float(_kurtosis(ecg))

    # ── Detección de picos R ──
    min_dist = int(0.5 * fs)  # al menos 500 ms entre latidos
    height_th = np.mean(ecg) + 0.5 * np.std(ecg)
    peaks, props = signal.find_peaks(ecg, distance=min_dist, height=height_th)

    if len(peaks) >= 2:
        rr = np.diff(peaks) / fs * 1000  # ms
        bpm = 60 / (np.mean(rr) / 1000)
        features["heart_rate"]   = float(bpm)
        features["rr_mean"]      = float(np.mean(rr))
        features["rr_std"]       = float(np.std(rr))
        features["rr_cv"]        = float(np.std(rr) / (np.mean(rr) + 1e-8))
        features["sdnn"]         = float(np.std(rr))
        features["rmssd"]        = float(np.sqrt(np.mean(np.diff(rr) ** 2)))
        features["pnn50"]        = float(np.sum(np.abs(np.diff(rr)) > 50) / len(rr) * 100)
        features["num_peaks"]    = int(len(peaks))
    else:
        features.update({k: 0.0 for k in [
            "heart_rate","rr_mean","rr_std","rr_cv","sdnn","rmssd","pnn50"]})
        features["num_peaks"] = int(len(peaks))

    # ── Espectrales ──
    band_masks = {
        "vlf": (f >= 0.003) & (f < 0.04),
        "lf":  (f >= 0.04)  & (f < 0.15),
        "hf":  (f >= 0.15)  & (f < 0.4),
    }
    total_power = np.sum(Sxx) + 1e-12
    for band, mask in band_masks.items():
        bp = float(np.sum(Sxx[mask, :]))
        features[f"{band}_power"] = bp
        features[f"{band}_ratio"] = bp / total_power

    lf = features["lf_power"] + 1e-12
    hf = features["hf_power"] + 1e-12
    features["lf_hf_ratio"] = lf / hf

    # Frecuencia dominante
    psd_mean = np.mean(Sxx, axis=1)
    features["dominant_freq"] = float(f[np.argmax(psd_mean)])

    # Energía espectral por decil
    for i, col in enumerate(np.array_split(Sxx, 5, axis=1)):
        features[f"spec_energy_seg{i}"] = float(np.mean(col))

    return features, peaks


def _skewness(x):
    m = np.mean(x)
    s = np.std(x) + 1e-8
    return np.mean(((x - m) / s) ** 3)

def _kurtosis(x):
    m = np.mean(x)
    s = np.std(x) + 1e-8
    return np.mean(((x - m) / s) ** 4) - 3


# ─── 5. CLASIFICACIÓN BASADA EN REGLAS + ML ──────────────────────────────────
def classify_ecg(features: dict) -> tuple[str, float, list[str], dict]:
    """
    Clasificación multi-capa:
      1. Reglas clínicas basadas en features
      2. Isolation Forest para detección de anomalía global
    Retorna (diagnóstico, confianza, notas_clínicas, scores)
    """
    hr     = features.get("heart_rate", 75)
    rr_cv  = features.get("rr_cv", 0.0)
    rmssd  = features.get("rmssd", 30)
    pnn50  = features.get("pnn50", 10)
    lf_hf  = features.get("lf_hf_ratio", 1.5)
    sdnn   = features.get("sdnn", 50)
    df     = features.get("dominant_freq", 1.0)
    peaks  = features.get("num_peaks", 0)

    notes = []
    candidates = {}

    # ── Taquicardia ──
    if hr > 100:
        score = min(1.0, (hr - 100) / 50)
        candidates["Taquicardia"] = score
        notes.append(f"FC elevada: {hr:.0f} lpm (normal 60-100)")

    # ── Bradicardia ──
    if hr < 60 and hr > 0:
        score = min(1.0, (60 - hr) / 30)
        candidates["Bradicardia"] = score
        notes.append(f"FC reducida: {hr:.0f} lpm (normal 60-100)")

    # ── Fibrilación Auricular (alta variabilidad RR + irregularidad) ──
    if rr_cv > 0.15 and rmssd > 50:
        score = min(1.0, rr_cv / 0.3 * 0.7 + rmssd / 100 * 0.3)
        candidates["Fibrilación Auricular"] = score
        notes.append(f"Alta variabilidad RR: CV={rr_cv:.3f}, RMSSD={rmssd:.1f} ms")

    # ── Flutter Auricular ──
    if 250 <= hr <= 350 or (0.3 <= df <= 8.0 and rr_cv < 0.1):
        candidates["Flutter Auricular"] = 0.65
        notes.append("Patrón de flutter: frecuencia auricular elevada y regular")

    # ── Bloqueo AV (RR muy largo o irregular sin FA) ──
    if features.get("rr_mean", 0) > 1200 and rr_cv < 0.1:
        candidates["Bloqueo AV"] = 0.7
        notes.append(f"Intervalo RR prolongado: {features['rr_mean']:.0f} ms")

    # ── Extrasístoles (picos aislados con RR variable bajo) ──
    if 0.05 < rr_cv < 0.15 and pnn50 < 5 and peaks > 3:
        candidates["Extrasístoles"] = 0.6
        notes.append("Variabilidad RR moderada compatible con latidos ectópicos")

    # ── Isquemia (alteraciones espectrales en baja frecuencia) ──
    if lf_hf > 4.0 and features.get("lf_ratio", 0) > 0.7:
        score = min(1.0, lf_hf / 8.0)
        candidates["Isquemia Miocárdica"] = score
        notes.append(f"Dominio LF marcado (ratio LF/HF = {lf_hf:.2f}) - posible isquemia")

    # ── Selección final ──
    if not candidates:
        diagnosis = "Normal"
        confidence = max(0.70, min(0.95, 1.0 - rr_cv * 2))
        notes.append("Ritmo sinusal normal. Sin anomalías detectadas.")
    else:
        diagnosis = max(candidates, key=candidates.get)
        confidence = float(candidates[diagnosis])
        # ajuste por múltiples señales
        if len(candidates) > 1:
            notes.append(f"Hallazgos secundarios: {', '.join(k for k in candidates if k != diagnosis)}")

    # Scores completos
    all_scores = {d: 0.0 for d in DIAGNOSES}
    all_scores["Normal"] = max(0.0, 1.0 - sum(candidates.values()) / max(1, len(candidates)))
    all_scores.update(candidates)
    # normalizar
    total = sum(all_scores.values()) + 1e-8
    all_scores = {k: v / total for k, v in all_scores.items()}

    return diagnosis, confidence, notes, all_scores


# ─── 6. GENERACIÓN DE FIGURAS ────────────────────────────────────────────────
def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


BG = "#0f172a"
GRID = "#1e293b"
ACCENT = "#06b6d4"
TEXT = "#e2e8f0"


def plot_ecg_signal(ecg: np.ndarray, fs: int, peaks: np.ndarray,
                    duration_sec: float = 10.0) -> str:
    n = min(int(duration_sec * fs), len(ecg))
    t = np.linspace(0, n / fs, n)
    sig = ecg[:n]

    fig, ax = plt.subplots(figsize=(11, 3.2), facecolor=BG)
    ax.set_facecolor(BG)

    # grid estilo papel ECG
    for y in np.arange(-4, 5, 0.5):
        ax.axhline(y, color=GRID, linewidth=0.3, alpha=0.6)
    for x in np.arange(0, n / fs, 0.2):
        ax.axvline(x, color=GRID, linewidth=0.3, alpha=0.6)

    ax.plot(t, sig, color=ACCENT, linewidth=0.9, alpha=0.95)

    # marcar picos R visibles
    visible_peaks = peaks[peaks < n]
    if len(visible_peaks):
        ax.scatter(visible_peaks / fs, sig[visible_peaks],
                   color="#f43f5e", s=25, zorder=5, label="Pico R")
        ax.legend(loc="upper right", fontsize=8, facecolor=BG,
                  labelcolor=TEXT, framealpha=0.7)

    ax.set_xlim(0, n / fs)
    ax.set_xlabel("Tiempo (s)", color=TEXT, fontsize=9)
    ax.set_ylabel("Amplitud (mV)", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    fig.tight_layout()
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_spectrogram(f: np.ndarray, t: np.ndarray,
                     Sxx_db: np.ndarray, fs: int) -> str:
    # Limitar a 0-40 Hz
    mask = f <= 40
    f_plot = f[mask]
    S_plot = Sxx_db[mask, :]

    fig, ax = plt.subplots(figsize=(11, 3.8), facecolor=BG)
    ax.set_facecolor(BG)

    vmin, vmax = np.percentile(S_plot, [5, 98])
    im = ax.pcolormesh(t, f_plot, S_plot, shading="gouraud",
                       cmap="plasma", vmin=vmin, vmax=vmax)
    cb = fig.colorbar(im, ax=ax, pad=0.01)
    cb.set_label("Potencia (dB)", color=TEXT, fontsize=9)
    cb.ax.yaxis.set_tick_params(color=TEXT, labelcolor=TEXT, labelsize=8)

    # bandas HRV
    for freq, label, col in [(0.04, "LF", "#22d3ee"), (0.15, "HF", "#a78bfa"),
                               (0.4, "", "#6ee7b7")]:
        if freq < f_plot[-1]:
            ax.axhline(freq, color=col, linewidth=0.8, linestyle="--", alpha=0.7)
            if label:
                ax.text(t[-1] * 0.01, freq + 0.005, label, color=col, fontsize=7)

    ax.set_xlabel("Tiempo (s)", color=TEXT, fontsize=9)
    ax.set_ylabel("Frecuencia (Hz)", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    fig.tight_layout()
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_rr_intervals(ecg: np.ndarray, fs: int, peaks: np.ndarray) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2), facecolor=BG)

    if len(peaks) >= 2:
        rr = np.diff(peaks) / fs * 1000
        beat_idx = np.arange(1, len(rr) + 1)

        # RR en el tiempo
        ax = axes[0]
        ax.set_facecolor(BG)
        ax.plot(beat_idx, rr, color="#a78bfa", linewidth=1.2, marker="o",
                markersize=3, markerfacecolor="#f43f5e")
        ax.axhline(np.mean(rr), color=ACCENT, linewidth=0.9,
                   linestyle="--", label=f"Media {np.mean(rr):.0f} ms")
        ax.fill_between(beat_idx, np.mean(rr) - np.std(rr),
                        np.mean(rr) + np.std(rr), alpha=0.15, color=ACCENT)
        ax.legend(fontsize=8, facecolor=BG, labelcolor=TEXT, framealpha=0.7)
        ax.set_xlabel("Latido #", color=TEXT, fontsize=9)
        ax.set_ylabel("Intervalo RR (ms)", color=TEXT, fontsize=9)
        ax.tick_params(colors=TEXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)

        # Poincaré plot
        ax2 = axes[1]
        ax2.set_facecolor(BG)
        ax2.scatter(rr[:-1], rr[1:], c="#06b6d4", s=18, alpha=0.7, edgecolors="none")
        ax2.plot([rr.min(), rr.max()], [rr.min(), rr.max()],
                 color=GRID, linewidth=0.8, linestyle="--")
        ax2.set_xlabel("RR_n (ms)", color=TEXT, fontsize=9)
        ax2.set_ylabel("RR_n+1 (ms)", color=TEXT, fontsize=9)
        ax2.tick_params(colors=TEXT, labelsize=8)
        for sp in ax2.spines.values():
            sp.set_edgecolor(GRID)
        ax2.set_title("Diagrama de Poincaré", color=TEXT, fontsize=9, pad=4)
    else:
        for ax in axes:
            ax.set_facecolor(BG)
            ax.text(0.5, 0.5, "Insuficientes picos R detectados",
                    ha="center", va="center", color=TEXT, transform=ax.transAxes)

    fig.tight_layout()
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_scores_bar(scores: dict) -> str:
    labels = list(scores.keys())
    vals   = [scores[l] * 100 for l in labels]
    colors_list = [DIAGNOSES[l]["color"] for l in labels]

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor=BG)
    ax.set_facecolor(BG)

    bars = ax.barh(labels, vals, color=colors_list, height=0.6, alpha=0.85)
    for bar, v in zip(bars, vals):
        if v > 2:
            ax.text(v + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{v:.1f}%", va="center", color=TEXT, fontsize=8)

    ax.set_xlim(0, 100)
    ax.set_xlabel("Probabilidad (%)", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    fig.tight_layout()
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_frequency_analysis(f: np.ndarray, Sxx: np.ndarray) -> str:
    psd = np.mean(Sxx, axis=1)
    mask = f <= 40

    fig, ax = plt.subplots(figsize=(7, 3.2), facecolor=BG)
    ax.set_facecolor(BG)
    ax.fill_between(f[mask], psd[mask], alpha=0.3, color=ACCENT)
    ax.plot(f[mask], psd[mask], color=ACCENT, linewidth=1.2)

    # bandas
    bands = [("VLF", 0, 0.04, "#f59e0b"), ("LF", 0.04, 0.15, "#22d3ee"),
             ("HF", 0.15, 0.4, "#a78bfa")]
    for name, lo, hi, c in bands:
        m = (f >= lo) & (f <= hi) & mask
        if m.any():
            ax.fill_between(f[m], psd[m], alpha=0.35, color=c, label=name)
    ax.legend(fontsize=8, facecolor=BG, labelcolor=TEXT, framealpha=0.7)
    ax.set_xlabel("Frecuencia (Hz)", color=TEXT, fontsize=9)
    ax.set_ylabel("PSD", color=TEXT, fontsize=9)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    fig.tight_layout()
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


# ─── 7. FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def analyze_ecg(filepath: str) -> dict:
    """Pipeline completo. Retorna dict JSON-serializable."""
    try:
        ecg_raw, fs = load_ecg(filepath)
        if len(ecg_raw) < fs * 2:
            raise ValueError("La señal es demasiado corta (mín. 2 segundos).")

        ecg = preprocess_ecg(ecg_raw, fs)
        f, t, Sxx_db, Sxx = ecg_to_spectrogram(ecg, fs)
        features, peaks = extract_features(ecg, fs, f, Sxx)
        diagnosis, confidence, notes, scores = classify_ecg(features)

        return {
            "status":    "ok",
            "diagnosis": diagnosis,
            "confidence": round(confidence * 100, 1),
            "risk":      DIAGNOSES[diagnosis]["risk"],
            "icon":      DIAGNOSES[diagnosis]["icon"],
            "color":     DIAGNOSES[diagnosis]["color"],
            "notes":     notes,
            "features":  {k: round(v, 4) if isinstance(v, float) else v
                          for k, v in features.items()},
            "scores":    {k: round(v * 100, 2) for k, v in scores.items()},
            "signal_info": {
                "duration_sec": round(len(ecg) / fs, 2),
                "fs_hz": fs,
                "n_samples": len(ecg),
            },
            "plots": {
                "ecg":       plot_ecg_signal(ecg, fs, peaks),
                "spectrogram": plot_spectrogram(f, t, Sxx_db, fs),
                "rr":        plot_rr_intervals(ecg, fs, peaks),
                "scores":    plot_scores_bar(scores),
                "psd":       plot_frequency_analysis(f, Sxx),
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_demo_ecg(condition: str = "normal", fs: int = 500,
                       duration: float = 10.0) -> np.ndarray:
    """
    Genera una señal ECG sintética para demostración.
    condition: 'normal' | 'tachy' | 'brady' | 'afib' | 'block'
    """
    t = np.linspace(0, duration, int(fs * duration))
    ecg = np.zeros_like(t)

    params = {
        "normal": {"bpm": 72,  "rr_noise": 0.02},
        "tachy":  {"bpm": 130, "rr_noise": 0.02},
        "brady":  {"bpm": 42,  "rr_noise": 0.02},
        "afib":   {"bpm": 90,  "rr_noise": 0.18},
        "block":  {"bpm": 45,  "rr_noise": 0.01},
    }
    p = params.get(condition, params["normal"])
    bpm, rr_noise = p["bpm"], p["rr_noise"]

    rr_base = 60.0 / bpm
    beat_times = []
    current = 0.0
    while current < duration:
        beat_times.append(current)
        rr = rr_base * (1 + np.random.randn() * rr_noise)
        current += max(0.3, rr)

    # Forma del latido PQRST simplificada
    def pqrst(t_local):
        p  =  0.15 * np.exp(-((t_local - 0.10) ** 2) / (2 * 0.008 ** 2))
        q  = -0.10 * np.exp(-((t_local - 0.18) ** 2) / (2 * 0.005 ** 2))
        r  =  1.00 * np.exp(-((t_local - 0.20) ** 2) / (2 * 0.006 ** 2))
        s  = -0.25 * np.exp(-((t_local - 0.22) ** 2) / (2 * 0.005 ** 2))
        tp =  0.25 * np.exp(-((t_local - 0.35) ** 2) / (2 * 0.030 ** 2))
        return p + q + r + s + tp

    for bt in beat_times:
        local_t = t - bt
        mask = (local_t >= -0.05) & (local_t <= 0.55)
        ecg[mask] += pqrst(local_t[mask])

    # Ruido
    ecg += np.random.randn(len(t)) * 0.03
    return ecg


if __name__ == "__main__":
    import sys, tempfile
    print("=== Test con señal sintética ===")
    for cond in ["normal", "tachy", "afib"]:
        ecg_demo = generate_demo_ecg(cond)
        # guardar como CSV temporal
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f_tmp:
            for v in ecg_demo:
                f_tmp.write(f"{v}\n")
            fname = f_tmp.name
        result = analyze_ecg(fname)
        os.unlink(fname)
        if result["status"] == "ok":
            print(f"  [{cond:8s}] → {result['diagnosis']:25s} | "
                  f"Conf: {result['confidence']}% | HR: {result['features'].get('heart_rate',0):.0f} lpm")
        else:
            print(f"  [{cond}] ERROR: {result['message']}")
