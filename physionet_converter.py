"""
Conversor PhysioNet/MIT-BIH → CSV
Descarga un registro real de ECG desde PhysioNet y lo convierte
al formato CSV que entiende CardioScan AI.

Requisitos:
    pip install wfdb numpy

Uso:
    python physionet_converter.py 100
    python physionet_converter.py 100 --canal 0
    python physionet_converter.py 100 --duracion 30
    python physionet_converter.py --listar
"""

import argparse
import os
import sys

try:
    import wfdb
    import numpy as np
except ImportError:
    print("📦 Instalando wfdb y numpy...")
    os.system(f"{sys.executable} -m pip install wfdb numpy -q")
    import wfdb
    import numpy as np


# ─── Registros recomendados por condición ────────────────────────────────────
REGISTROS_RECOMENDADOS = {
    "mitdb": {
        "descripcion": "MIT-BIH Arrhythmia Database (arritmias variadas)",
        "registros": {
            "100": "Normal / ritmo sinusal",
            "101": "Normal con algunas extrasístoles",
            "200": "Múltiples tipos de arritmias",
            "201": "Bloqueo de rama, extrasístoles",
            "203": "Fibrilación auricular + ruido",
            "210": "Extrasístoles ventriculares frecuentes",
            "217": "Marcapasos + extrasístoles ventriculares",
            "221": "Fibrilación auricular",
            "223": "Múltiples arritmias supraventriculares",
            "232": "Bloqueo AV de segundo grado",
        }
    },
    "afdb": {
        "descripcion": "MIT-BIH Atrial Fibrillation Database (fibrilación auricular)",
        "registros": {
            "04015": "Fibrilación auricular paroxística",
            "04043": "Fibrilación auricular paroxística",
            "08378": "Fibrilación auricular",
        }
    },
    "nsrdb": {
        "descripcion": "MIT-BIH Normal Sinus Rhythm Database (ritmo normal)",
        "registros": {
            "16265": "Ritmo sinusal normal",
            "16272": "Ritmo sinusal normal",
            "16273": "Ritmo sinusal normal",
        }
    },
}


def listar_registros():
    print("\n" + "═" * 70)
    print("  REGISTROS RECOMENDADOS PARA PROBAR CardioScan AI")
    print("═" * 70)
    for db, info in REGISTROS_RECOMENDADOS.items():
        print(f"\n📁 {db}  —  {info['descripcion']}")
        for reg, desc in info["registros"].items():
            print(f"     {reg:8s} → {desc}")
    print("\n" + "─" * 70)
    print("  Uso:  python physionet_converter.py <registro> --db <basedatos>")
    print("  Ej:   python physionet_converter.py 100 --db mitdb")
    print("  Ej:   python physionet_converter.py 04015 --db afdb")
    print("─" * 70 + "\n")


def convertir_registro(registro: str, db: str = "mitdb",
                        canal: int = 0, duracion: float = None,
                        salida: str = None):
    """
    Descarga un registro de PhysioNet y lo convierte a CSV.

    Args:
        registro: nombre del registro (ej. '100')
        db: base de datos en PhysioNet (ej. 'mitdb', 'afdb', 'nsrdb')
        canal: índice del canal ECG a extraer (0 o 1 usualmente)
        duracion: segundos a extraer (None = todo el registro)
        salida: nombre del archivo CSV de salida
    """
    print(f"\n🌐 Descargando registro '{registro}' de la base '{db}'...")
    print("   (esto puede tardar unos segundos la primera vez)")

    try:
        # Descarga directa desde los servidores de PhysioNet
        record = wfdb.rdrecord(registro, pn_dir=db)
    except Exception as e:
        print(f"\n❌ Error al descargar: {e}")
        print("\nVerifica:")
        print("  1. Que el nombre del registro sea correcto")
        print("  2. Que el nombre de la base de datos sea correcto")
        print("  3. Que tengas conexión a internet")
        print("\nEjecuta 'python physionet_converter.py --listar' para ver opciones válidas.")
        return None

    fs = record.fs
    n_canales = record.p_signal.shape[1]
    print(f"✅ Descargado: {record.record_name}")
    print(f"   Frecuencia de muestreo : {fs} Hz")
    print(f"   Canales disponibles    : {n_canales} {record.sig_name}")
    print(f"   Duración total         : {record.sig_len / fs:.1f} s")

    if canal >= n_canales:
        print(f"⚠️  Canal {canal} no existe, usando canal 0.")
        canal = 0

    señal = record.p_signal[:, canal]

    if duracion is not None:
        n_muestras = int(duracion * fs)
        señal = señal[:n_muestras]
        print(f"   Recortado a            : {duracion} s ({n_muestras} muestras)")

    # Nombre de salida
    if salida is None:
        salida = f"{db}_{registro}_canal{canal}.csv"

    np.savetxt(salida, señal, fmt="%.6f")
    print(f"\n💾 Guardado como: {salida}")
    print(f"   Listo para subir a CardioScan AI (http://localhost:5050)")

    # Si hay anotaciones, mostrarlas como referencia
    try:
        ann = wfdb.rdann(registro, "atr", pn_dir=db)
        tipos = {}
        for sym in ann.symbol:
            tipos[sym] = tipos.get(sym, 0) + 1
        print(f"\n📋 Anotaciones clínicas de referencia (cardiólogos):")
        simbolos = {
            "N": "Normal", "L": "Bloqueo rama izq.", "R": "Bloqueo rama der.",
            "A": "Extrasístole auricular", "V": "Extrasístole ventricular",
            "F": "Fusión", "/": "Marcapasos", "f": "Fusión marcapasos",
            "j": "Escape juncional", "E": "Escape ventricular",
            "a": "Extrasístole auricular aberrante", "J": "Escape juncional prematuro",
            "S": "Extrasístole supraventricular", "e": "Escape auricular",
            "Q": "No clasificado",
        }
        for sym, count in sorted(tipos.items(), key=lambda x: -x[1]):
            desc = simbolos.get(sym, sym)
            print(f"     {sym:3s} ({desc:30s}): {count} latidos")
    except Exception:
        pass  # no todos los registros tienen anotaciones .atr

    return salida


def main():
    parser = argparse.ArgumentParser(
        description="Convierte registros de PhysioNet a CSV para CardioScan AI"
    )
    parser.add_argument("registro", nargs="?", help="Nombre del registro (ej. 100)")
    parser.add_argument("--db", default="mitdb",
                        help="Base de datos: mitdb, afdb, nsrdb (default: mitdb)")
    parser.add_argument("--canal", type=int, default=0,
                        help="Índice del canal ECG (default: 0)")
    parser.add_argument("--duracion", type=float, default=30.0,
                        help="Segundos a extraer (default: 30, usa 0 para todo)")
    parser.add_argument("--salida", default=None,
                        help="Nombre del archivo CSV de salida")
    parser.add_argument("--listar", action="store_true",
                        help="Listar registros recomendados")

    args = parser.parse_args()

    if args.listar or not args.registro:
        listar_registros()
        return

    duracion = None if args.duracion == 0 else args.duracion
    convertir_registro(args.registro, db=args.db, canal=args.canal,
                       duracion=duracion, salida=args.salida)


if __name__ == "__main__":
    main()
