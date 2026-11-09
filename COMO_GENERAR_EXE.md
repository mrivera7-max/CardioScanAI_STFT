# Cómo generar CardioScanAI.exe

## Resumen

Vamos a usar **PyInstaller**, una herramienta que empaqueta tu aplicación
Python (con Flask, numpy, scipy, matplotlib, scikit-learn y todo lo
necesario) en un único archivo `.exe` que funciona en cualquier PC con
Windows **sin necesitar Python instalado**.

---

## Archivos nuevos que recibiste

| Archivo | Función |
|---|---|
| `cardioscan_launcher.py` | Punto de entrada especial — abre el navegador automáticamente |
| `cardioscan.spec` | Configuración de PyInstaller (qué incluir en el .exe) |
| `build_exe.bat` | Script que automatiza todo el proceso de construcción |

Estos van **junto** a los archivos que ya tienes (`app.py`, `ecg_pipeline.py`,
`templates/`, etc.) en la misma carpeta.

---

## Paso 1 — Verifica la carpeta

Tu carpeta de proyecto debe verse así:

```
files\
├── app.py
├── ecg_pipeline.py
├── run.py
├── physionet_converter.py
├── cardioscan_launcher.py      ← nuevo
├── cardioscan.spec             ← nuevo
├── build_exe.bat               ← nuevo
├── README.md
└── templates\
    └── index.html
```

## Paso 2 — Ejecuta el generador automático

Haz **doble clic** en `build_exe.bat`

Esto hará automáticamente:
1. Verificar que Python esté instalado
2. Instalar las dependencias del proyecto (flask, numpy, scipy, etc.)
3. Instalar PyInstaller
4. Limpiar compilaciones anteriores
5. Generar el ejecutable (tarda 2-5 minutos)

Verás una ventana de consola con el progreso. Al final debe decir:

```
============================================================
  EJECUTABLE GENERADO CON EXITO
============================================================

  Ubicacion: dist\CardioScanAI.exe
```

## Paso 3 — Usa tu ejecutable

El archivo está en:

```
files\dist\CardioScanAI.exe
```

**Cópialo a donde quieras** (Escritorio, USB, otra PC con Windows) y
ábrelo con doble clic. Automáticamente:
- Arranca el servidor
- Abre tu navegador en `http://127.0.0.1:5050` (o el puerto que esté libre)
- Muestra la interfaz de CardioScan AI lista para usar

Para **cerrar la aplicación**, cierra la ventana de consola negra que se
abrió (o presiona `Ctrl+C` dentro de ella).

---

## Solución de problemas

### "pyinstaller no se reconoce como un comando" (si lo ejecutas manualmente)

Usa el `.bat` en vez de comandos manuales — ya maneja la instalación. Si
insistes en hacerlo a mano:

```cmd
pip install pyinstaller
pyinstaller cardioscan.spec --noconfirm
```

### El .exe tarda mucho en abrir la primera vez

Es normal — PyInstaller empaqueta numpy, scipy y matplotlib, que son
pesados (~150-300 MB). La primera ejecución descomprime archivos
temporales; las siguientes son más rápidas.

### Windows Defender / antivirus bloquea el .exe

Los ejecutables generados por PyInstaller a veces son marcados como
sospechosos por antivirus (falso positivo común, por cómo empaquetan el
código). Si pasa:
1. Haz clic en "Más información" → "Ejecutar de todas formas"
2. O agrega una excepción en Windows Defender para esa carpeta

### Quiero un ícono personalizado para el .exe

1. Consigue un archivo `.ico` (puedes convertir un PNG en
   [convertio.co](https://convertio.co/png-ico/) o similar)
2. Ponlo en la carpeta del proyecto, por ejemplo `icono.ico`
3. Edita `cardioscan.spec`, busca la línea:
   ```python
   icon=None,
   ```
   y cámbiala a:
   ```python
   icon='icono.ico',
   ```
4. Vuelve a ejecutar `build_exe.bat`

### El .exe es muy grande (300+ MB)

Es esperado: incluye Python completo + todas las librerías científicas.
Si necesitas reducirlo, podrías:
- Usar `--onedir` en vez de un solo archivo (PyInstaller crea una carpeta
  con varios archivos en vez de un único .exe, pero arranca más rápido)
- Quitar matplotlib/scikit-learn si simplificas el pipeline (no recomendado,
  son el corazón del sistema)

---

## ¿Quiero distribuir esto a otras personas?

El `.exe` generado funciona en cualquier Windows de **la misma arquitectura**
(normalmente 64 bits, que es el estándar actual). No necesitan instalar
Python ni nada — solo copiar el archivo y hacer doble clic.

> **Nota:** un PyInstaller `.exe` generado en Windows solo funciona en
> Windows. No es compatible con macOS ni Linux — para esos sistemas
> habría que generar el ejecutable por separado en una máquina de ese
> sistema operativo.
