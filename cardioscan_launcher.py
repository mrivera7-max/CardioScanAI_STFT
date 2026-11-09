"""
CardioScan AI — Punto de entrada para el ejecutable (.exe)
Abre el servidor y lanza el navegador automáticamente.
"""

import sys
import os
import threading
import webbrowser
import time
import socket


def get_base_dir():
    """
    Devuelve la carpeta base correcta tanto si se ejecuta como script
    normal de Python, como si se ejecuta empaquetado por PyInstaller.
    """
    if getattr(sys, "frozen", False):
        # Ejecutándose como .exe empaquetado
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def find_free_port(preferred=5050):
    """Si el puerto preferido está ocupado, busca uno libre."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s.close()
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.bind(("127.0.0.1", 0))
        port = s2.getsockname()[1]
        s2.close()
        return port


def open_browser(url, delay=1.5):
    """Espera a que el servidor arranque y abre el navegador."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    base_dir = get_base_dir()
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    port = find_free_port(5050)
    url = f"http://127.0.0.1:{port}"

    print(r"""
   ____              _ _       _____
  / __ \            | (_)     / ____|
 | |  | |__ _ _ __ __| |_  ___| |     ___  _ __
 | |  | / _` | '__/ _` | |/ _ \ |    / _ \| '_ \
 | |__| | (_| | | | (_| | | (_) | |___| (_) | | | |
  \____/\__,_|_|  \__,_|_|\___/ \_____\___/|_| |_|  AI

  Clasificación de Enfermedades Cardiovasculares
  ECG → Espectrograma → Machine Learning
""")
    print(f"  🫀  Iniciando CardioScan AI…")
    print(f"  🌐  Abriendo en: {url}")
    print(f"  ⏳  Esto puede tardar unos segundos en la primera ejecución…\n")
    print("  Para CERRAR la aplicación, cierra esta ventana o presiona Ctrl+C.\n")
    print("─" * 60)

    # Abrir navegador en un hilo separado, sin bloquear el arranque del servidor
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    from app import app
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
