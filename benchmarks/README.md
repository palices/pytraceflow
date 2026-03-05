# Benchmarks PyTraceFlow (English)

Steps to compare the optimized PyTraceFlow (`feature/optimize`) versus `main` using the sample `samples/complex/complex_app.py` and the synthetic workload.

## Prerequisites
- Run from the repo root.
- Python on PATH.
- Checkout the branch you want to test.

## 1) Quick comparison with complex sample

`feature/optimize` (uses call-threshold flushing):
```bash
python pytraceflow.py -s samples/complex/complex_app.py -o bench-output/feature.json --flush-interval 5 --flush-call-threshold 500 --skip-inputs
```

`main` (no threshold, same compatible flags):
```bash
python pytraceflow.py -s samples/complex/complex_app.py -o bench-output/main.json --flush-interval 5 --skip-inputs
```

Timings appear on STDERR as `[FlowTrace] Profiling finished in ...s`. JSON traces land in `bench-output/`.

## 2) Large synthetic workload (stress test)

First, generate many calls:
```bash
python benchmarks/trace_stress.py --iterations 500 --depth 4 --breadth 3 --work 40 > /dev/null
```

Then profile with each branch:

`feature/optimize` (uses call threshold, fewer serializations):
```bash
python pytraceflow.py -s benchmarks/trace_stress.py -o bench-output/feature_stress.json --flush-interval 5 --flush-call-threshold 500 --skip-inputs --iterations 500 --depth 4 --breadth 3 --work 40
```

`main` (same config, no threshold):
```bash
python pytraceflow.py -s benchmarks/trace_stress.py -o bench-output/main_stress.json --flush-interval 5 --skip-inputs --iterations 500 --depth 4 --breadth 3 --work 40
```

## 3) Compare profiles with cProfile (optional)

Use the helper to generate baseline vs tracer profiles:
```bash
python benchmarks/profile_compare.py --target benchmarks/trace_stress.py --target-args "--iterations 500 --depth 4 --breadth 3 --work 40" --skip-inputs --flush-interval 5 --flush-call-threshold 500
```

Outputs: `bench-output/baseline.prof`, `bench-output/traced.prof`, `bench-output/pft.json`.
Inspect with:
```bash
python -m pstats bench-output/traced.prof
```

## Notes
- `--flush-interval 5` is a good starting point to cut I/O. Set `--flush-interval 0` to disable periodic flushing (in `feature/optimize` it will only flush at end or when threshold triggers).
- `--skip-inputs` avoids serializing locals and lowers overhead when objects are large.

---

# Benchmarks PyTraceFlow (Español)

Pasos para comparar el PyTraceFlow optimizado (`feature/optimize`) contra el de `main` usando el sample `samples/complex/complex_app.py` y el workload sintético.

## Requisitos previos
- Estar en la raíz del repo.
- Python disponible en el PATH.
- Rama correspondiente chequeada según la prueba.

## 1) Comparativa rápida con sample complejo

Rama `feature/optimize` (usa el nuevo umbral de llamadas):
```bash
python pytraceflow.py -s samples/complex/complex_app.py -o bench-output/feature.json --flush-interval 5 --flush-call-threshold 500 --skip-inputs
```

Rama `main` (sin umbral, flags compatibles):
```bash
python pytraceflow.py -s samples/complex/complex_app.py -o bench-output/main.json --flush-interval 5 --skip-inputs
```

Los tiempos se muestran en STDERR como `[FlowTrace] Profiling finished in ...s`. Los JSON quedan en `bench-output/`.

## 2) Workload sintético grande (stress test)

Primero genera un workload que produzca muchas llamadas:
```bash
python benchmarks/trace_stress.py --iterations 500 --depth 4 --breadth 3 --work 40 > /dev/null
```

Luego perfila con cada rama:

Rama `feature/optimize` (aprovecha flush por umbral y reduce serializaciones):
```bash
python pytraceflow.py -s benchmarks/trace_stress.py -o bench-output/feature_stress.json --flush-interval 5 --flush-call-threshold 500 --skip-inputs --iterations 500 --depth 4 --breadth 3 --work 40
```

Rama `main` (misma configuración, sin umbral):
```bash
python pytraceflow.py -s benchmarks/trace_stress.py -o bench-output/main_stress.json --flush-interval 5 --skip-inputs --iterations 500 --depth 4 --breadth 3 --work 40
```

## 3) Comparar perfiles con cProfile (opcional)

Usa el helper para generar perfiles baseline vs tracer:
```bash
python benchmarks/profile_compare.py --target benchmarks/trace_stress.py --target-args "--iterations 500 --depth 4 --breadth 3 --work 40" --skip-inputs --flush-interval 5 --flush-call-threshold 500
```

Archivos resultantes: `bench-output/baseline.prof`, `bench-output/traced.prof`, `bench-output/pft.json`.
Analiza con:
```bash
python -m pstats bench-output/traced.prof
```

## Notas
- `--flush-interval 5` es un valor razonable para reducir E/S. Para desactivar flush periódico, usa `--flush-interval 0` (en `feature/optimize` solo se flushea al final o por umbral).
- `--skip-inputs` evita serializar locals y baja mucho el overhead cuando hay objetos grandes.
