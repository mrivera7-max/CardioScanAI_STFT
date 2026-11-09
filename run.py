#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   CardioScan AI — Clasificación de Enfermedades Cardiovasculares ║
║   ECG → Espectrograma → Machine Learning                         ║
╚══════════════════════════════════════════════════════════════════╝

Uso:
  python run.py            → inicia el servidor (puerto 5050)
  python run.py --port 8080
  python run.py --demo     → solo prueba el pipeline (sin servidor)
"""

import sys, os, subprocess, argparse

REQUIRED = [
    ("flask",      "flask"),
    ("numpy",      "numpy"),
    ("scipy",      "scipy"),
    ("matplotlib", "matplotlib"),
    ("sklearn",    "scikit-learn"),
    ("PIL",        "pillow"),
]


def check_and_install():
    print("🔍  Verificando dependencias…")
    missing = []
    for import_name, pkg_name in REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        print(f"📦  Instalando: {', '.join(missing)}")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--break-system-packages", "-q", *missing
        ])
        print("✅  Dependencias instaladas.")
    else:
        print("✅  Todas las dependencias están disponibles.")


def run_demo():
    """Prueba rápida del pipeline sin levantar servidor."""
    import tempfile, numpy as np
    from ecg_pipeline import analyze_ecg, generate_demo_ecg

    cases = [
        ("normal", "Ritmo Sinusal Normal"),
        ("tachy",  "Taquicardia"),
        ("brady",  "Bradicardia"),
        ("afib",   "Fibrilación Auricular"),
        ("block",  "Bloqueo AV"),
    ]

    print("\n" + "─" * 60)
    print("  PRUEBA DEL PIPELINE ECG")
    print("─" * 60)

    for cond, desc in cases:
        ecg = generate_demo_ecg(cond, fs=500, duration=12.0)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            for v in ecg:
                f.write(f"{v}\n")
            fname = f.name

        result = analyze_ecg(fname)
        os.unlink(fname)

        if result["status"] == "ok":
            hr  = result["features"].get("heart_rate", 0)
            diag = result["diagnosis"]
            conf = result["confidence"]
            risk = result["risk"]
            icon = result["icon"]
            print(f"  {icon}  {desc:<28s} → {diag:<25s} ({conf:4.1f}% · Riesgo {risk}  · {hr:.0f} lpm)")
        else:
            print(f"  ✗  {desc:<28s} → ERROR: {result['message']}")

    print("─" * 60)
    print("  Pipeline OK\n")


def main():
    parser = argparse.ArgumentParser(description="CardioScan AI — Servidor ECG")
    parser.add_argument("--port",  type=int, default=5050, help="Puerto HTTP (default: 5050)")
    parser.add_argument("--host",  default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--demo",  action="store_true", help="Solo ejecutar demo (sin servidor)")
    parser.add_argument("--debug", action="store_true", help="Modo debug de Flask")
    args = parser.parse_args()

    check_and_install()

    if args.demo:
        run_demo()
        return

    # ── Iniciar servidor ──────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  🫀  CardioScan AI                                       ║
║                                                          ║
║  URL:    http://localhost:{args.port:<5}                       ║
║  Host:   {args.host:<46} ║
╚══════════════════════════════════════════════════════════╝

  Presiona Ctrl+C para detener el servidor.
    """)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    from app import app
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
