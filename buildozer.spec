[app]

# ── Identificación ──────────────────────────────────────────────────────────
title       = Control Ganadero
package.name   = controlganadero
package.domain = com.hacienda

# ── Versión ─────────────────────────────────────────────────────────────────
version = 1.0

# ── Archivos fuente ─────────────────────────────────────────────────────────
source.dir = .
source.include_exts = py,html,css,js,png,jpg,jpeg,webp,json,txt

# Incluir carpetas de templates y static (excepto uploads que son datos del usuario)
source.include_patterns =
    app.py,
    exportar.py,
    main.py,
    templates/**,
    static/css/**,
    static/icons/**,
    static/manifest.json,
    static/sw.js,
    res/**

# Excluir archivos innecesarios en el APK
source.exclude_dirs = __pycache__, .git, .claude
source.exclude_patterns =
    ganado.db,
    static/uploads/**,
    run_out.txt,
    run_err.txt,
    cargar_datos_demo.py,
    iniciar.bat,
    run_prod.py,
    build_android.*,
    buildozer.spec

# ── Dependencias Python ──────────────────────────────────────────────────────
# p4a instala las dependencias transitivas (werkzeug, jinja2, etc.) via pip
requirements = python3,flask,reportlab,openpyxl,pillow

# ── Android ──────────────────────────────────────────────────────────────────
android.permissions = INTERNET
android.api    = 33
android.minapi = 26
android.ndk    = 25b
android.archs  = arm64-v8a

# Bootstrap WebView: crea una Activity con WebView que carga localhost:5000
p4a.bootstrap = webview

# Permite HTTP en 127.0.0.1 (Android 9+ bloquea HTTP por defecto)
android.add_manifest_application_attributes = android:networkSecurityConfig="@xml/network_security_config" android:usesCleartextTraffic="true"

# Recursos adicionales (network_security_config.xml)
android.add_res = res/

# ── Íconos ────────────────────────────────────────────────────────────────────
icon.filename       = %(source.dir)s/static/icons/icon-192.png
presplash.filename  = %(source.dir)s/static/icons/icon-512.png
presplash.lottie    = False

# ── Orientación ───────────────────────────────────────────────────────────────
orientation = all
fullscreen  = 0

# ── Opciones de build ─────────────────────────────────────────────────────────
android.release_artifact = apk

[buildozer]
log_level    = 2
warn_on_root = 0
