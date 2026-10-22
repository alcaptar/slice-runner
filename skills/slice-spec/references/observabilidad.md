# Cerebro de observabilidad de la slice

Reference-doc de `slice-spec`. Se carga **solo cuando el slicing detecta que hay senal que
disenar** (`reference-docs` + `context-management`), y tambien lo carga el **implementador** de
`slice-runner` cuando la slice tiene que instrumentar algo.

Dos partes: la **escalera** (universal, vale para cualquier repo) y el **stack concreto** (la
libreria de instrumentacion, el repo de alertas y el de paneles), que hay que averiguar en cada repo.

## Filosofia

Un cambio no esta hecho cuando pasa la CI: esta hecho cuando **puedes ver en produccion que hace lo
que pretendia**. Eso es *observability-driven development*: decides la telemetria **antes** de
implementar, la instrumentacion viaja **con** el codigo (no en una slice "de telemetria" futura), y
la usas para confirmar el cambio vivo.

**La senal tiene dos asserts, y por eso no basta con un criterio de aceptacion:**

| | assert | quien lo verifica | cuando |
|---|---|---|---|
| **Emision** | el codigo emite la metrica/log/span con sus labels | test + `slice-verifier` | pre-merge |
| **Valor vivo** | el contador sube / el error no aparece tras el deploy | quien despliega | post-deploy |

La emision es un **criterio de aceptacion normal** y falsable (borra la instrumentacion y el test
cae). El valor vivo **no es testeable**: por eso vive en su propia linea `SENAL:`, que declara
como se comprueba y que comprueba quien despliega.

## Cuando procede (y cuando no)

**Exige `SENAL`** si la slice cambia **comportamiento observable en produccion**: endpoint, consumer,
job/cronjob, flag que conmuta un camino, cambio de regla de negocio con efecto visible.

**Exenta** (declarandolo y justificandolo, `SENAL: exenta - <motivo>`):

- refactor puro sin cambio de comportamiento;
- value object o helper interno sin efecto observable propio;
- migracion de schema cuyo efecto aun no se usa (su verificacion es el `SELECT` del plan);
- panel de Grafana (no emite serie: se comprueba renderizando).

La exencion **se escribe**. Ausencia silenciosa no es exencion: es la senal que nadie penso.

**Vara de falsabilidad, mirando a prod:** *nombra la senal que cambiaria si esto se rompe vivo*. Si
no puedes nombrarla, la slice no es observable — y eso es un defecto de diseno que se arregla **aqui**,
en el slicing, no en el incidente.

## Escalera de senal

Baja un escalon **solo si el anterior no basta**. El escalon 1 existe para no instrumentar de mas:
la mayoria de las slices ya tienen senal y solo hay que **apuntar** a ella.

1. **¿Ya existe la senal gratis?** Si el codigo que tocas ya esta instrumentado por el framework o la
   libreria del repo, la serie ya existe. La `SENAL` apunta a ella: **cero codigo nuevo**.
2. **¿Basta enriquecer lo que ya emite?** Anadir un atributo al log, un label existente, un span
   extra. Coste minimo, sigue siendo la libreria.
3. **¿Hace falta senal de negocio nueva?** Metrica propia inyectada por DI, con su **test de
   emision**. Es codigo de produccion de **esta** slice, no de una futura.
4. **¿La libreria no lo expresa idiomaticamente?** Es un **gap de la libreria**: se declara y se
   resuelve o se acota **ahi**. Nunca una instrumentacion ad-hoc paralela a la libreria: duplicar el
   mecanismo es peor que el gap, porque el gap se arregla una vez y la duplicacion se hereda.

## El stack concreto de cada repo

La escalera es universal; lo que cambia de un repo a otro es **donde** vive cada escalon. Antes de
trocear, averigua con la persona o en el codigo tres cosas: que **libreria de instrumentacion** usa el
repo, en que **repo viven las alertas** y en cual **los paneles**.

### La libreria de instrumentacion

Lo primero es saber que emite ya **sin escribir una linea** (escalon 1). Lo tipico de una libreria de
instrumentacion madura:

| Primitiva | Emite |
|---|---|
| decorador de caso de uso | contador de ejecuciones y histograma de duracion, con labels estables (`component`, `service`), span de trazas y logs estructurados de inicio y fin |
| decorador de comando o job | lo mismo para procesos batch o cronjobs, mas el reporte de errores |
| middleware HTTP | contador de peticiones por metodo, ruta y estado, y la latencia; si la expone como histograma, sirve para ratios de buenos eventos en un SLI |
| integraciones de mensajeria | metricas de consumers y producers |
| logger configurado | logs JSON con los atributos de contexto ya namespaced |

Escalon 2 — enriquecer sin metrica nueva. Los nombres de abajo son ilustrativos: cada libreria tiene
los suyos.

```python
@traced_use_case(log_fields=["loan_id", "branch_code"])
class AjustarInventario:
    def execute(self, params: AjustarInventarioParams) -> None: ...
```

```python
with tracer.start_span("recalculo_disponibilidad"):
    ...
```

Escalon 3 — metrica de negocio propia. El puerto de metricas es **abstracto**: se inyecta, no se
instancia dentro del dominio.

```python
AJUSTES = Counter(
    "ejemplares_ajustados_total",
    "Ajustes del inventario de ejemplares aplicados.",
    ["motivo"],
)

class AjustarInventario:
    def __init__(self, metrics: MetricsPort) -> None:
        self._metrics = metrics

    def execute(self, params: AjustarInventarioParams) -> None:
        ...
        self._metrics.increment(AJUSTES, motivo=params.motivo)
```

Y su **test de emision** — el "observability test": no testea logica de negocio, testea que la
telemetria cumple el contrato. Sin mocks: un doble en memoria del puerto basta.

```python
def test_registra_el_ajuste_en_la_metrica() -> None:
    metrics = InMemoryMetrics()

    AjustarInventario(metrics=metrics).execute(un_ajuste(motivo="deterioro"))

    assert metrics.value_of("ejemplares_ajustados_total", motivo="deterioro") == 1
```

**Naming**: sigue la convencion que ya use el repo (`*_total` para contadores, las mismas labels
estables que el resto). **Nunca** un label derivado del nombre del pod: rompe en cada deploy.

**Gap de la libreria (escalon 4)**: si lo que necesitas no se puede expresar con la libreria (falta un
tipo de metrica, un decorador no cubre tu tipo de proceso, no hay forma de anadir un label), abre issue
en el repo de la libreria describiendo el caso y **dilo en la spec**. Un contador a mano en paralelo a
la libreria no es una solucion: es el gap, heredado.

### Alertas

Slice **propia**, siempre. Si las alertas viven en otro repo, es PR distinta por definicion, y
mezclarla con la metrica romperia la higiene del diff. Del repo de alertas hay que saber la ruta donde
va cada regla (normalmente por equipo y por entorno), las labels obligatorias que valida su CI y sus
controles.

**Una alerta es TDD-able de verdad.** Hay dos preguntas distintas: lint y validacion responden
*"¿parsea el YAML y compila el PromQL?"*; `promtool test rules` responde *"cuando estas metricas se
comportan asi, ¿dispara la alerta?"*. Escribe el test con `input_series` primero, mira que falla, y
luego la regla:

```yaml
rule_files:
  - rules.yml
evaluation_interval: 1m
tests:
  - input_series:
      - series: 'ejemplares_ajuste_fallido_total{deployment="catalogo-api"}'
        values: '0+1x10'
    alert_rule_test:
      - eval_time: 6m
        alertname: AjusteInventarioFallido
        exp_alerts:
          - exp_labels: {severity: warning, team: catalogo, deployment: catalogo-api}
```

Criterios de aceptacion tipicos de una slice de alerta: el test `promtool` que dispara con la serie
esperada, el que **no** dispara por debajo del umbral, labels obligatorias presentes y `for:`
no-cero.

`SENAL` tipica: `prometheus ALERTS{alertname="X"} presente y == 0 en 24h` — es decir, la
regla **cargo** y **no genera falsos positivos**. Es advisory a proposito: una alerta recien puesta que
dispara no es una regresion, te dice que el umbral esta mal calibrado.

### Paneles

Slice **propia**, la ultima de la cadena y la primera candidata a posponer.

Si el repo de paneles no tiene control mas alla de "el JSON parsea", es **capa eximida** (delta 1 de
`slice-runner`, como los modelos ORM): no fuerces test-first. El control es "JSON valido + el panel
renderiza y sus queries devuelven datos", y eso se comprueba tras el deploy. Su `SENAL` normalmente es
`exenta`, con el motivo escrito.

## Orden forzoso

No se puede alertar ni pintar una serie que nadie emite. No es preferencia, es dependencia:

```
slice-N    emite la senal (repo de app)        SENAL: la serie aparece con sus labels
    | deploy + quien despliega confirma la serie viva
slice-N+1  alerta (repo de alertas)           SENAL: ALERTS{alertname="X"} presente y == 0
slice-N+2  panel (repo de paneles)            SENAL: exenta - render manual
```

Coherente con **"Aislamiento de infra"** de `slicing.md` (PRs distintas: despliega, observa, y luego el
paso siguiente) y con el **test de despriorizacion**: el panel es exactamente la slice que puedes
posponer sin perder el core.

## Como se escribe la linea `SENAL:`

Texto libre **estructurado**, no un DSL. Quien despliega construye la query concreta, asi que basta
con ser inequivoco:

    SENAL: <fuente> <expresion o serie> ; <assert vivo con su ventana>

```
SENAL: prometheus rate(ejemplares_ajustados_total{motivo="deterioro"}[5m]) > 0 en 10m post-deploy
SENAL: elasticsearch logs con ajuste_rechazado y campo motivo presentes tras el primer rechazo
SENAL: prometheus ALERTS{alertname="AjusteInventarioFallido"} presente y == 0 en 24h
SENAL: exenta - refactor puro, ningun comportamiento cambia
```

Malas, y por que:

```
SENAL: se monitoriza con Grafana                 <- no nombra serie, ventana ni assert: no es refutable
SENAL: la latencia no empeora                    <- ¿que percentil, medido donde, contra que baseline?
SENAL: revisar que funcione                       <- prosa
```

## Anti-patterns

- **Alerta o panel en la misma PR que la metrica.** Repos distintos y ademas mezcla concerns; el
  orden forzoso existe porque la serie tiene que estar viva primero.
- **Alertar una serie que aun no ha llegado a prod**: la regla se evalua contra nada y no dispara
  nunca (o dispara al reves si es un `absent()`).
- **Instrumentacion ad-hoc paralela a la libreria** en vez de declarar el gap.
- **Declarar `SENAL` con lo que el test ya prueba** ("el contador se incrementa" es el criterio de
  emision, no la senal viva).
- **Dejar la telemetria para "la slice de observabilidad" del final**: es la aplazable que nunca llega,
  y es justo lo que este doc corrige de la heuristica 9.
- **`SENAL` ausente sin declarar exencion**: pasa desapercibida y quien despliega no sabe que
  mirar, sin que nadie lo haya decidido.
- **Metrica de alta cardinalidad** (ids de prestamo, emails, uuid como label): revienta Prometheus. Eso
  va al log estructurado o al span, no a un label.

## Fuentes

- Charity Majors, Liz Fong-Jones, George Miranda — *Observability Engineering*, cap. 11
  (Observability-Driven Development). Honeycomb — *Authors' Cut: Making the Move to ODD*.
- Splunk — *Observability-Driven Development Explained*. oneuptime — *ODD with OpenTelemetry*
  (observability contract: "estos tests no testean logica de negocio; testean que la telemetria que
  produce el codigo cumple el contrato").
