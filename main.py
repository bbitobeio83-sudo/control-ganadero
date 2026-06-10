"""
Punto de entrada para Android (buildozer webview bootstrap).
En PC este archivo no se usa; se ejecuta app.py directamente.
"""
import os
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))


def _setup_android():
    """Configura rutas persistentes en Android para que DB y fotos
    sobrevivan actualizaciones del APK."""
    try:
        from android.storage import app_storage_path
        data = app_storage_path()

        # Base de datos en almacenamiento persistente
        os.environ.setdefault('GANADO_DB', os.path.join(data, 'ganado.db'))

        # Fotos/logo en almacenamiento persistente via symlink
        uploads_persistent = os.path.join(data, 'uploads')
        os.makedirs(os.path.join(uploads_persistent, 'animales'), exist_ok=True)

        uploads_in_static = os.path.join(_HERE, 'static', 'uploads')

        if os.path.islink(uploads_in_static):
            # Ya existe el symlink; actualizarlo si apunta a otro lugar
            if os.readlink(uploads_in_static) != uploads_persistent:
                os.unlink(uploads_in_static)
                os.symlink(uploads_persistent, uploads_in_static)
        elif os.path.isdir(uploads_in_static):
            # Directorio real (primera instalación o post-actualización):
            # mover archivos existentes al almacenamiento persistente
            import shutil
            for item in os.listdir(uploads_in_static):
                src = os.path.join(uploads_in_static, item)
                dst = os.path.join(uploads_persistent, item)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
            shutil.rmtree(uploads_in_static)
            os.symlink(uploads_persistent, uploads_in_static)
        else:
            os.symlink(uploads_persistent, uploads_in_static)

    except ImportError:
        pass  # No estamos en Android


def _start_flask():
    _setup_android()
    os.chdir(_HERE)
    sys.path.insert(0, _HERE)

    from app import app, init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, threaded=True, use_reloader=False)


def _wait_ready(timeout=30):
    """Espera hasta que Flask responda o se agote el tiempo."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://127.0.0.1:5000/', timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# Iniciar Flask en hilo daemon
threading.Thread(target=_start_flask, daemon=True).start()

# Esperar a que Flask esté listo
_wait_ready()

# Mostrar en el WebView embebido
import webview
webview.load_url('http://127.0.0.1:5000/')
