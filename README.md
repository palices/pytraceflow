<p align="center" style="margin-bottom: 0;">
  <img src="https://raw.githubusercontent.com/palices/flowtrace/main/images/logo_pytfw_simple_nobrillo_small.png" alt="PyTraceFlow logo" width="320" style="max-width:100%; height:auto;">
</p>
# PyTraceFlow.

[![PyPI](https://img.shields.io/pypi/v/pytraceflow.svg?label=PyPI&color=blue&cacheSeconds=300)](https://pypi.org/project/pytraceflow/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python)](https://pypi.org/project/pytraceflow/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-green)](#)

PyTraceFlow is a trace visualizer designed as a "post-mortem debugger": instead of pausing and resuming, it captures calls (inputs, outputs, caller, module, duration, errors) into a hierarchical JSON so you can inspect them later without re-running.

[![PyTraceFlow overview](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow.jpg)
[![Call details panel](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_calls.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_calls.jpg)

## Quick start (3 steps)
0. Copy files pytraceflow.py and pytraceflow_visual.py to your project folder
1. Capture script execution to JSON: `python pytraceflow.py -s <PATH_TO_PYTHON_SCRIPT> -o <JSON_FILENAME>`
2. Render the HTML viewer: `python pytraceflow_visual.py -i <JSON_FILENAME> -o <HTML_OUTPUT_FILENAME>`
[![Call details panel](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_visual.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_visual.jpg)
3. Install PyCharm plugin (optional) located at `plugins/pycharm/Pytraceflow_plugin-1.0.0.zip`. See PyCharm plugin section
[![Call details panel](https://raw.githubusercontent.com/palices/flowtrace/main/images/pycharm_plugin.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pycharm_plugin.jpg)
4. Optional export to OTLP/Jaeger (HTTP 4318): `python export_otlp.py -i <JSON_FILE_NAME> --endpoint http://localhost:4318/v1/traces --service pytraceflow-complex`
[![Call details panel](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_menu.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_menu.jpg)
[![Call details panel](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_spans.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_spans.jpg)
## Basic flow
1. Profile a script: `python pytraceflow.py -s your_script.py -o pft.json`
2. Generate the viewer: `python pytraceflow_visual.py -i pft.json -o pft.html`
3. Open `pft.html` and browse:
   - Search terms: opens the matching node in a floating panel.
   - Expand/collapse nodes; open calls.
   - Controls to show/hide badges, Python internals, language (es/en), and light/dark mode.

### Passing script arguments
- PyTraceFlow uses `argparse.parse_known_args`; any arguments it does not recognize are forwarded to the profiled script (no `--` needed).
- To avoid ambiguity when script flags look like PyTraceFlow flags, add an explicit separator: `--`.
- Example with options: `python pytraceflow.py -s samples/basic/basic_sample.py --customer "ana maria" --tier gold --coffee 3`
- Example with positionals: `python pytraceflow.py -s samples/basic/basic_positional_sample.py "juan perez" silver 1 2 0 0.18`
- Example with separator (recommended when mixing flags):  
  `python pytraceflow.py -s my_app.py --flush-interval 5 --skip-inputs -- --flag-for-script foo --another 1`

## Features
- Captures inputs/outputs, caller, module, duration, and errors.
- Groups instances and nested calls while preserving hierarchy.
- Search with highlighting and floating panels; option to hide Python internals.
- Dark mode by default, quick controls, and multi-language.
- Performance knobs: `--flush-interval` (seconds, <=0 disables background flush), `--flush-every-call` (legacy, slower), `--log-flushes` (stderr).
- Overhead controls: memoria desactivada por defecto; habilita con `--with-memory` (usa psutil + tracemalloc), o combina `--no-tracemalloc` / `--no-memory`. `--skip-inputs` evita serializar args/kwargs; `--skip-outputs` evita serializar valores de retorno.
- Root entry now records total runtime; STDERR line: `[PyTraceFlow] Profiling finished in X.XXXs (script=...)`.
- Export existing traces to OTLP/Jaeger via `export_otlp.py`, with span names enriched by module and instance id to make nested calls distinct in Jaeger UI.

## PyCharm plugin
- Packaged ZIP: `plugins/pycharm/Pytraceflow_plugin-1.0.0.zip`.
- Install: PyCharm Settings > Plugins > gear > Install Plugin from Disk > select the ZIP > restart.
- Use: set a breakpoint, click the yellow diamond gutter icon to open the trace popup (tree + detail pane).
- Generate traces from the popup with "Generate Pytraceflow json"; the command field is editable (default `python pytraceflow.py -s <script> <args>`).
- More details in `plugins/readme.md`.

## CLI options
- `-s/--script` (required): target script path.
- `-o/--output`: JSON output path (default `pft.json`).
- `--flush-interval`: seconds between background flushes; `<=0` disables thread (default `1.0`).
- `--flush-every-call`: force flush on every event (slow; legacy).
- `--log-flushes`: log each flush to stderr.
- `--with-memory`: enable memory snapshots (psutil + tracemalloc). Default is off; expect slower runs when enabled.
- `--no-memory`: disable memory snapshots.
- `--no-tracemalloc`: keep psutil but skip tracemalloc.
- `--skip-inputs`: do not serialize call inputs/locals.
- `--skip-outputs`: do not serialize return values.
- OTLP export (optional, requires `opentelemetry-*`): `--export-otlp-endpoint http://localhost:4318/v1/traces`, `--export-otlp-service myapp`, repeat `--export-otlp-header key=value` for extra headers.
- Any other args are forwarded to the profiled script.

### Usage examples
- Default fast run: `python pytraceflow.py -s samples/basic/basic_sample.py -o pft.json`
- With memory metrics: `python pytraceflow.py -s samples/basic/basic_sample.py --with-memory --flush-interval 2.0`
- Minimal overhead: `python pytraceflow.py -s samples/basic/basic_sample.py --flush-interval 0 --skip-inputs --skip-outputs`
- Legacy per-call flush with logs: `python pytraceflow.py -s samples/basic/basic_sample.py --flush-every-call --log-flushes`
- Memory via psutil only: `python pytraceflow.py -s samples/basic/basic_sample.py --with-memory --no-tracemalloc`
- Export to OTLP/HTTP: `python pytraceflow.py -s samples/basic/basic_sample.py --export-otlp-endpoint http://localhost:4318/v1/traces --export-otlp-service pytraceflow-sample`
- Export a saved trace to Jaeger (OTLP/HTTP, port 4318): `python export_otlp.py -i pft.json --endpoint http://localhost:4318/v1/traces --service pytraceflow-sample`
- Export with custom headers (auth/tenant): `python export_otlp.py -i pft.json --endpoint http://localhost:4318/v1/traces --service pytraceflow-sample --header Authorization=Bearer_TOKEN --header X-Tenant=acme`

## Included examples
- `script.py` basic example.
- `complex_app.py` with modules `demo/...` (prices, taxes, discounts).
- `conc_demo.py` with CPU-bound (multiprocessing) and IO-bound (threads) to view concurrent traces.
- `basic_positional_sample.py` shows the same flow using positional arguments.
- `error_sample.py` intentionally fails (missing config) to show the error badge.

## Backlog / ideas
- Filters by module/class/time.
- Export filtered views.

## License
MIT License. See `LICENSE` for full text.

---

PyTraceFlow es un visualizador de trazas de ejecucion, pensado como un "debugger post-mortem": en lugar de parar y reanudar, captura las llamadas (inputs, outputs, caller, modulo, duracion, errores) en un JSON jerarquico para inspeccionarlo despues sin reejecutar.

[![Vista general de PyTraceFlow](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow.jpg)
[![Panel de detalle de llamadas](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_calls.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_calls.jpg)

## Inicio rápido (3 pasos)
1. Capturar el ejemplo complejo a JSON: `python pytraceflow.py -s <RUTA_SCRIPT_PYTHON> -o <NOMBRE_FICHERO_JSON>`
2. Generar el visor HTML: `python pytraceflow_visual.py -i <NOMBRE_FICHERO_JSON> -o <NOMBRE_FICHERO_HTML>`
[![Panel visual de llamadas](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_visual.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_visual.jpg)
3. Install Pycharm plugin (optional) 
4. (Opcional) Exportar a OTLP/Jaeger (HTTP 4318): `python export_otlp.py -i <NOMBRE_FICHERO_JSON> --endpoint http://localhost:4318/v1/traces --service pytraceflow-complex`
[![Menu de exportacion a OTLP/Jaeger](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_menu.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_menu.jpg)
[![Spans exportados a Jaeger](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_spans.jpg)](https://raw.githubusercontent.com/palices/flowtrace/main/images/pytraceflow_to_otlp_spans.jpg)

## Flujo basico
1. Perfilar un script: `python pytraceflow.py -s tu_script.py -o pft.json`
2. Generar visor: `python pytraceflow_visual.py -i pft.json -o pft.html`
3. Abrir `pft.html` y navegar:
   - Buscar trminos: abre el nodo coincidente en panel flotante.
   - Expandir/colapsar nodos; abrir calls.
   - Controles para mostrar/ocultar badges, internals de Python, idioma (es/en) y modo claro/oscuro.

### Pasar argumentos al script
- PyTraceFlow usa `argparse.parse_known_args`; cualquier argumento que no reconoce se reenvía al script perfilado (no hace falta `--`).
- Para evitar ambigüedad cuando los flags del script se parecen a los de PyTraceFlow, añade el separador explícito `--`.
- Ejemplo con opciones: `python pytraceflow.py -s samples/basic/basic_sample.py --customer "ana maria" --tier gold --coffee 3`
- Ejemplo con posicionales: `python pytraceflow.py -s samples/basic/basic_positional_sample.py "juan perez" silver 1 2 0 0.18`
- Ejemplo con separador (recomendado cuando se mezclan flags):  
  `python pytraceflow.py -s mi_app.py --flush-interval 5 --skip-inputs -- --flag-del-script foo --otra 1`

## Caracteristicas
- Captura inputs/outputs, caller, modulo, duracion y errores.
- Agrupa instancias y llamadas anidadas preservando jerarquia.
- Buscador con resaltado y paneles flotantes; opcion para ocultar internals de Python.
- Modo oscuro por defecto, controles rapidos y multilenguaje.
- Ajustes de performance: `--flush-interval` (segundos, <=0 desactiva flush en background), `--flush-every-call` (modo anterior, mas lento), `--log-flushes` (stderr).
- Controles de overhead: memoria viene desactivada por defecto; `--with-memory` la habilita (psutil + tracemalloc), combinable con `--no-tracemalloc` / `--no-memory`. `--skip-inputs` evita serializar args/kwargs; `--skip-outputs` evita serializar valores de retorno.
- La llamada raiz registra el tiempo total; se imprime en STDERR `[PyTraceFlow] Profiling finished in X.XXXs (script=...)`.
- Export de trazas existentes a OTLP/Jaeger con `export_otlp.py`; los spans incluyen módulo e id de instancia para distinguir llamadas anidadas en Jaeger.

## Plugin para PyCharm
- ZIP listo para instalar: `plugins/pycharm/Pytraceflow_plugin-1.0.0.zip`.
- Instalar: PyCharm Configuración > Plugins > rueda > Install Plugin from Disk > seleccionar el ZIP > reiniciar.
- Uso: pon un breakpoint y haz clic en el icono amarillo del margen para abrir el popup de trazas (arbol + panel de detalle).
- Genera trazas desde el popup con "Generate Pytraceflow json"; el comando es editable (por defecto `python pytraceflow.py -s <script> <args>`).
- Detalles ampliados en `plugins/readme.md`.

## Opciones CLI
- `-s/--script` (obligatorio): ruta del script a perfilar.
- `-o/--output`: ruta del JSON de salida (por defecto `pft.json`).
- `--flush-interval`: segundos entre flushes en background; `<=0` desactiva el hilo (por defecto `1.0`).
- `--flush-every-call`: fuerza flush en cada evento (lento; legado).
- `--log-flushes`: loguea cada flush a stderr.
- `--with-memory`: habilita snapshots de memoria (psutil + tracemalloc). Por defecto está apagado; al activarlo las ejecuciones serán más lentas.
- `--no-memory`: desactiva snapshots de memoria.
- `--no-tracemalloc`: deja psutil pero omite tracemalloc.
- `--skip-inputs`: no serializa inputs/locals de las llamadas.
- `--skip-outputs`: no serializa valores de retorno.

### Overhead presets
- Minimal overhead: `--flush-interval 0 --skip-inputs --skip-outputs`
- Capture timings + outputs only: `--skip-inputs --flush-interval 5`
- Capture timings + inputs only: `--skip-outputs --flush-interval 5`

### Perfiles de overhead
- Overhead mínimo: `--flush-interval 0 --skip-inputs --skip-outputs`
- Tiempos + outputs (sin inputs): `--skip-inputs --flush-interval 5`
- Tiempos + inputs (sin outputs): `--skip-outputs --flush-interval 5`
- Export OTLP (opcional, requiere `opentelemetry-*`): `--export-otlp-endpoint http://localhost:4318/v1/traces`, `--export-otlp-service miapp`, headers extra con `--export-otlp-header clave=valor` (repetible).
- Cualquier otro argumento se reenvía al script perfilado.

### Ejemplos de uso
- Ejecución rápida por defecto: `python pytraceflow.py -s samples/basic/basic_sample.py -o pft.json`
- Con métricas de memoria: `python pytraceflow.py -s samples/basic/basic_sample.py --with-memory --flush-interval 2.0`
- Overhead mínimo: `python pytraceflow.py -s samples/basic/basic_sample.py --flush-interval 0 --skip-inputs --skip-outputs`
- Flush por llamada con logs: `python pytraceflow.py -s samples/basic/basic_sample.py --flush-every-call --log-flushes`
- Solo psutil (sin tracemalloc): `python pytraceflow.py -s samples/basic/basic_sample.py --with-memory --no-tracemalloc`
- Export a OTLP/HTTP: `python pytraceflow.py -s samples/basic/basic_sample.py --export-otlp-endpoint http://localhost:4318/v1/traces --export-otlp-service pytraceflow-sample`
- Exportar un JSON ya capturado a Jaeger (OTLP/HTTP, puerto 4318): `python export_otlp.py -i pft.json --endpoint http://localhost:4318/v1/traces --service pytraceflow-sample`
- Exportar con cabeceras extra (auth/tenant): `python export_otlp.py -i pft.json --endpoint http://localhost:4318/v1/traces --service pytraceflow-sample --header Authorization=Bearer_TOKEN --header X-Tenant=acme`

## Ejemplos incluidos
- `script.py` ejemplo basico.
- `complex_app.py` con modulos `demo/...` (precios, impuestos, descuentos).
- `conc_demo.py` con CPU-bound (multiproceso) e IO-bound (hilos) para ver trazas concurrentes.
- `basic_positional_sample.py` muestra el mismo flujo usando argumentos posicionales.
- `error_sample.py` falla adrede (config faltante) para ver el badge de error.
- `error_internal_sample.py` falla dentro de una llamada interna (`validate_config`) para ver errores anidados.

## Pendientes / ideas
- Filtros por mdulo/clase/tiempo.
- Export de vistas filtradas.
- Integracin con spans/telemetra.

## Licencia
MIT License. Ver `LICENSE` para el texto completo.

---
Author: Tony F.

