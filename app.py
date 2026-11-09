"""
Servidor web Flask para interfaz de análisis ECG.
"""

import os, sys, json, tempfile, base64
from pathlib import Path

# ── Instalar Flask si no está disponible ──────────────────────────────────────
try:
    from flask import Flask, request, jsonify, send_file
except ImportError:
    os.system(f"{sys.executable} -m pip install flask --break-system-packages -q")
    from flask import Flask, request, jsonify, send_file

from ecg_pipeline import analyze_ecg, generate_demo_ecg
import numpy as np

def _get_base_dir():
    """Funciona tanto en ejecución normal como empaquetada con PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

BASE_DIR = _get_base_dir()

app = Flask(__name__,
            static_folder=str(BASE_DIR / "static"),
            template_folder=str(BASE_DIR / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

UPLOAD_DIR = Path(tempfile.gettempdir()) / "ecg_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED = {".csv", ".txt", ".wav", ".npy", ".dat"}


@app.route("/")
def index():
    return send_file(str(BASE_DIR / "templates" / "index.html"))


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No se recibió archivo."}), 400

    f = request.files["file"]
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED:
        return jsonify({"status": "error",
                        "message": f"Formato no soportado: {ext}. Use .csv, .txt, .wav, .npy"}), 400

    tmp = UPLOAD_DIR / f"ecg_{os.getpid()}_{f.filename}"
    try:
        f.save(str(tmp))
        result = analyze_ecg(str(tmp))
        return jsonify(result)
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


@app.route("/api/demo/<condition>")
def api_demo(condition: str):
    allowed = {"normal", "tachy", "brady", "afib", "block"}
    if condition not in allowed:
        return jsonify({"status": "error", "message": "Condición no válida."}), 400

    ecg = generate_demo_ecg(condition, fs=500, duration=12.0)
    tmp = UPLOAD_DIR / f"demo_{condition}_{os.getpid()}.csv"
    try:
        np.savetxt(str(tmp), ecg, fmt="%.6f")
        result = analyze_ecg(str(tmp))
        result["demo_condition"] = condition
        return jsonify(result)
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


@app.route("/api/export_report", methods=["POST"])
def export_report():
    """Genera un reporte PDF simple en texto."""
    from datetime import datetime
    data = request.json or {}
    operator = (data.get("operator_name") or "").strip()

    lines = [
        "=" * 60,
        "  REPORTE DE ANÁLISIS ELECTROCARDIOGRÁFICO",
        "  Sistema de Detección de Anomalías Cardíacas",
        "=" * 60,
    ]
    if operator:
        lines.append(f"  Operador / Paciente: {operator}")
    lines.append(f"  Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lines += [
        "=" * 60,
        f"  Diagnóstico:   {data.get('diagnosis','N/A')}",
        f"  Confianza:     {data.get('confidence','N/A')}%",
        f"  Nivel de riesgo: {data.get('risk','N/A')}",
        "",
        "  Hallazgos clínicos:",
    ]
    for note in data.get("notes", []):
        lines.append(f"    • {note}")
    lines += [
        "",
        "  Métricas cardíacas:",
        f"    Frecuencia cardíaca : {data.get('features',{}).get('heart_rate',0):.0f} lpm",
        f"    SDNN                : {data.get('features',{}).get('sdnn',0):.1f} ms",
        f"    RMSSD               : {data.get('features',{}).get('rmssd',0):.1f} ms",
        f"    pNN50               : {data.get('features',{}).get('pnn50',0):.1f} %",
        f"    Razón LF/HF         : {data.get('features',{}).get('lf_hf_ratio',0):.2f}",
        "",
        "  NOTA: Este análisis es de apoyo diagnóstico.",
        "  No reemplaza la evaluación de un cardiólogo.",
        "=" * 60,
        "  CardioScan AI",
        "  Diseñado y desarrollado por:",
        "  Ing. María Fernanda Rivera Sanclemente",
        "  UDI 2025 ",
        "=" * 60,
    ]
    text = "\n".join(lines)
    tmp_report = UPLOAD_DIR / "reporte_ecg.txt"
    tmp_report.write_text(text, encoding="utf-8")
    return send_file(str(tmp_report), as_attachment=True,
                     download_name="reporte_ecg.txt", mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n🫀  Servidor ECG iniciado → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
