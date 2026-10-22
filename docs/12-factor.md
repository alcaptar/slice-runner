# 12-factor-agents: donde encaja este repo, y que implica

> **Lectura fechada, no vara de medir.** Es la auditoria del repo contra los doce factores tal como
> estaba el 2026-07-31, más el spike que la cerró. De aquí salió la decisión de convertir el
> orquestador en un programa, y **ese** es su valor: decir que se pensaba entonces y por que. Lo que
> cita puede haberse retirado desde entonces -y parte lo esta-; se lee como lo que era ese día y **no
> se reescribe** para ponerlo al día. Lo vigente vive en `README.md` y en `docs/conventions/`.

Referencia: [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents). Los doce
factores se leyeron enteros el 2026-07-31, no de memoria; las citas salen de esa lectura.

Este documento tiene dos mitades que se necesitan: una **auditoria** del repo contra los doce factores,
y el **spike medido** que responde a la pregunta que la auditoria abre. Sin la primera, el spike no se
sabe por que existe; sin el segundo, la auditoria sería una opinion.

## TL;DR

1. **Los factores 1, 4 y 9 ya se cumplen**, y en el 9 el repo va más allá de lo que el texto pide.
2. **El factor 2 es la tesis del repo** (prompts como código versionado), con un hueco: no hay evals.
3. **Los factores 2, 3, 5, 6, 8 y 12 presuponen que el loop es tuyo.** Aquí no lo era: el loop era el
   de Claude Code y el orquestador eran las ~600 líneas del `SKILL.md` del runner (retirado; el
   programa que lo sustituye es `src/slice_runner/`), prosa que un modelo interpretaba dentro de la
   sesión de la persona. **Esa fue la causa raíz** del problema de contexto y de casi todos los
   defectos de abajo.
4. **Los huecos no son doce, son tres**: los factores 5, 6, 8 y 12 apuntan todos al mismo sitio.
5. El spike valida que `claude -p` es la función sin estado que hace falta, **y añade un requisito que
   no estaba previsto**: el aislamiento del implementador hay que decidirlo antes de escribir el
   orquestador, no después.
6. **Acotar las herramientas de cada llamada es a la vez la garantía y la palanca de coste**: darle al
   verificador solo lo que necesita para juzgar hace que su incapacidad de ejecutar sea estructural
   **y** parte el coste por la mitad. No hay que elegir entre seguro y barato.

## Mapeo factor por factor

| Factor | Estado | Evidencia |
|---|---|---|
| 1. Lenguaje natural a llamadas de herramienta | **Cumple** | el nucleo de la skill de seguimiento de despliegues es "el código determinista tiene la soberania"; `controles.py` e `issue_body.py`, retirados con el flujo viejo, también lo eran. El modelo propone, el exit code decide |
| 2. Duena de tus prompts | **Cumple, con hueco** | Skills versionadas aquí, con `~/.claude/` por symlink; `tests/test_skill_contracts.py` valida contratos escritos en `.md`. Falta lo que el factor pide además: *"testing y evaluaciones como código regular"* |
| 3. Duena de tu ventana de contexto | **Parcial, conocido** | Muy trabajado (salida de build a disco, relato largo fuera del `SKILL.md`, subagentes desechables). Residual: el orquestador vive en la sesión del harness, que no es del repo. Declarado como fase 2 en las notas de diseño de entonces |
| 4. Las herramientas son salida estructurada | **Cumple** | El veredicto del verificador era un objeto validado por `controles.py verify-verdict` (retirado con el flujo viejo). Frontera más debil: la lista de rutas del implementador volvia en prosa, con `pr-hygiene` como red |
| 5. Unificar estado de ejecución y de negocio | **Incumple** | Cluster A, abajo |
| 6. Lanzar / pausar / reanudar | **Parcial** | Pausa y reanuda bien **entre** slices (el issue es el estado). **Dentro** de una slice no hay reanudación: cluster A |
| 7. Contactar humanos con llamadas de herramienta | **Incumple** | Cluster B, abajo |
| 8. Duena de tu control de flujo | **Incumple** | Los diez pasos y los presupuestos son prosa interpretada. Contradice el principio propio del repo, "lo que es regla exacta pasa a script, sin excepciones" |
| 9. Compactar errores en la ventana de contexto | **Cumple, y va más allá** | `controles.py controles --out` mandaba el log a disco y devolvía ruta (retirado con el flujo viejo); el error entero llegaba al implementador y **nada** llegaba al que juzga. El factor pedia compactar; el repo además aislaba |
| 10. Agentes pequeños y enfocados | **Parcial, conocido** | Tres skills y dos agentes definidos (estos últimos, retirados) bien acotados, pero el orquestador tiene diez pasos con reintentos, por encima del rango de 3-10 que el factor recomienda |
| 11. Disparar desde cualquier sitio | **Incumple** | El estado ya vive en un issue de GitHub, pero el disparador solo existe en la línea de comandos. Compone con el cluster B |
| 12. El agente como reductor sin estado | **Parcial** | Los nucleos puros existen (`deploy_core.py`; el de `issue_body.py`, retirado con el flujo viejo, también lo era). El orquestador no es un reductor: su estado es implícito en su contexto. El propio autor marca este factor como didactico |

## Los tres clusters

### Cluster A — el estado de ejecución no esta unificado con el de negocio (factores 5, 6, 8, 12)

El issue tiene el estado de **negocio** (que slice, en que fase macro) pero no el de **ejecución**: en
que paso va, cuanto presupuesto queda, que hallazgos no bloqueantes están abiertos. Cuatro defectos que
salen de leer el código, no de suponer:

- **Una slice `en-curso` al reanudar no tenía guion.** `_elige_slice` en `issue_body.py` (retirado con
  el flujo viejo) devolvía la primera slice con estado distinto de `mergeada`, lo que incluye
  `en-curso`, `bloqueada: *` y `abortada: *`. El paso 1 del `SKILL.md` solo daba procedimiento para
  `pendiente` y `esperando-merge`. Con una slice `en-curso` se re-elegia, el `git switch -c` del paso 4
  chocaba con la rama existente, y el paso 5 reimplementaba desde cero sin saber que se hizo.
- **Los presupuestos se resetean en silencio.** Los 2 reintentos de controles, los 2 del verificador y
  los 3 ticks de la ventana de gracia de la integración continua viven **solo** en el contexto del
  orquestador. Al reanudar o compactar vuelven a cero sin que nada avise.
- **Bajo `/loop`, una slice bloqueada se re-elige indefinidamente.** El `max_consecutive_failures`
  figura en las notas de diseño de entonces como guardrail pendiente, no construido.
- **`metrics.py record` solo escribe al cerrar**, así que una slice que muere a mitad no deja rastro ni
  de haber existido.

Y hay una confesión en el propio repo que este cluster resuelve: la ventana de gracia de la integración
continua se declaró **excepción** a "lo que es regla exacta pasa a script", y el motivo escrito es
exactamente *"la ventana es una cuenta entre invocaciones, y `ci-status` es de un tiro y sin estado a
propósito"*. Con estado de ejecución durable, ese motivo desaparece.

### Cluster B — el contacto humano no es una acción durable (factores 7, 11)

El go/no-go del paso 3 es "espera respuesta del usuario" en el chat. Las notas de diseño de entonces ya lo
admitían: *"bajo `/loop` ese control humano ya es ficción"*. El factor 7 da el arreglo con nombre:
contactar al humano es una **acción estructurada con estado persistido** (pausa, notifica, reanuda por
disparador), no una pregunta en una conversación que nadie mira. El factor 11 añade que el disparador
debería vivir donde ya vive el estado.

### Cluster C — los prompts son código de primera categoría pero no tienen evals (factor 2)

La pieza de más valor del repo, el verificador, se calibra con impresiones: smoke manual y metricas
terminales por slice. `docs/maturity-map.md` pone como siguiente paso *"validar el verificador en runs
reales hasta ganarle confianza"*, que es precisamente lo que un eval convierte en medible. Hoy no se
puede: el verificador es un subagente invocado desde una conversación, no una función
`diff -> veredicto`.

## Que NO aplica, dicho a propósito

Estampar los doce factores sería `ai-slop`. Lo que queda fuera y por que:

- **Factores 3 y 10 en su parte residual**: el orquestador vive en un harness ajeno. No es un defecto
  de diseño que se arregle escribiendo prosa; es la consecuencia de no ser dueño del loop, y solo se
  arregla cambiando eso.
- **Factor 12 como reductor literal**: el propio documento lo marca como *"mostly just for fun"*. Su
  parte útil es el cluster A.
- **Factor 11 como canales multiples** (Slack, correo, mensajeria): fuera de alcance para uso personal.
  Lo que si aplica es que el disparador viva donde vive el estado.

## Los dos loops, y solo uno merece ser propio

La conclusión de la auditoria no es "añadir una sección de estado al issue". Es que **el orquestador
está en el sitio equivocado**. Pero hay dos loops distintos:

- **El loop de orquestación** (elegir slice, implementar, controlar, verificar, abrir pull request,
  esperar la integración continua, presupuestos, reintentos): **debe ser propio**. Es determinista, es
  donde vive el estado, y hoy lo ejecuta un modelo leyendo prosa.
- **El loop de codificar** (leer, editar, ejecutar, iterar): **no**. Reconstruirlo es un proyecto grande
  y saldria peor que Claude Code. Ahi el modelo es el intermediario del factor 1: recibe un prompt,
  devuelve estructura, muere.

El criterio de corte por skill es **si el valor está en la conversación o en el loop**:

| Skill | Donde esta su valor | Destino |
|---|---|---|
| `skills/slice-spec/SKILL.md` | La conversación con una persona | Sigue siendo skill. Ser dueño del loop aquí no compra nada y cuesta justo lo que la hace buena |
| `SKILL.md` del runner (retirado) | El loop | Programa (`src/slice_runner/`) |
| la skill de seguimiento de despliegues | El loop de ticks, con nucleo puro ya escrito | Programa, o skill fina sobre uno |

Y el coste de la transición es menor de lo que parece: `deploy_core.py`, `metrics.py`,
`discover_controles.py` y `discover_conventions.py` **ya son** el nucleo determinista y los puertos,
con sus tests -y entonces también lo eran `controles.py` e `issue_body.py`, hoy retirados-. Lo que se
escribe nuevo es el aggregate del run, el puerto del agente de código y el entrypoint. Lo que se
**borra** es la mayor parte del `SKILL.md` del runner: la prosa de control de flujo pasa a código con
tests.

## Spike: `claude -p` como llamada sin estado (2026-07-31)

**Por que existe.** Todo lo anterior depende de una afirmación que no se puede dar por buena leyendo
documentación: que `claude -p` sirve como función sin estado y con salida estructurada. Se midió en un
playground aislado, fuera del repo. **15 llamadas, 1,07 dolares, todo con haiku** -el modelo más debil
a propósito: lo que cumpla ahi lo cumple un modelo mejor-.

### Lo que se confirmo

**`--json-schema` hace cumplir el contrato del veredicto.** Cuatro ejecuciones con el system prompt
real del entonces agente definido `slice-verifier` (hoy retirado; 2.223 palabras, transferido tal cual
con `--append-system-prompt`) sobre un diff con una violación de convención plantada:

| Ejecución | Contrato (`verify-verdict`) | Veredicto del juez | alta/media/baja | Coste | Duración |
|---|---|---|---|---|---|
| 1 | exit 0, PASA | FALLA | 4/0/0 | 0,109 $ | 51 s |
| 2 | exit 0, PASA | FALLA | 2/0/0 | 0,096 $ | 77 s |
| 3 | exit 0, PASA | FALLA | 2/0/0 | 0,109 $ | 86 s |
| 4 | exit 0, PASA | FALLA | 3/0/0 | 0,070 $ | 56 s |

Cuatro de cuatro pasan **el validador que entonces ya existia en el repo**, sin desenvolver prosa ni
reinvocar. `result` es una cadena con el objeto, consumible tal cual por `controles.py verify-verdict`
(retirado con el flujo viejo). Esto ataca directamente lo que entonces declaraba el `SKILL.md` del
runner: *"el cumplimiento del formato es estocastico"*. Con el esquema desaparece, y con el
probablemente el contador `--descartes-verify` entero. Varia el **número** de hallazgos, no el
veredicto, que es la varianza que se espera de un juez.

**Hay tres flags de herramientas y solo uno restringe de verdad.** No son variaciones del mismo
mecanismo: hacen tres cosas distintas, y la intuición lleva a los dos equivocados.

- **`--tools 'Read,Grep,Glob'` es el que restringe**: fija el conjunto integrado disponible, así que el
  resto **no existe**. Con eso puesto y un prompt que le pide explicitamente buscar cualquier vía de
  ejecución, el agente enumero sus tres herramientas y se rindio **en un turno**, con
  `permission_denials` vacío. Es lo que el `allowed-tools` del frontmatter prometia y no daba (lo refuto
  el smoke del 2026-07-27, en las notas de diseño de entonces).
- **No cubre las herramientas de servidores externos** (el flag dice "del conjunto integrado"): con
  `--tools` acotado a tres, los servidores MCP seguian enteros en el inventario que el propio
  agente recito. Para dejarlos fuera hace falta además **`--strict-mcp-config`** sin pasar ninguna
  configuración.
- **`--disallowedTools Bash` también produce ausencia**, y además **se hereda al subagente**: el agente
  intento escapar delegando en uno, y fallo por eso. Verificado, y es load-bearing -sin esa herencia,
  delegar sería la puerta de atras del control entero-. Sirve como denegación puntual, pero como
  mecanismo principal obliga a mantener una lista negra que se queda corta cada vez que aparece una
  herramienta nueva.
- **`--allowedTools 'Read,Grep,Glob'` no restringe: pre-aprueba.** Con eso puesto, `Bash` seguia
  disponible, el agente lo invoco, quedó registrado en `permission_denials`, y la llamada **acabo
  pidiendo aprobación humana** en vez de devolver un veredicto. En un proceso no interactivo eso es una
  llamada perdida, no un fallo seguro.

**El preambulo no es irreducible: acotar el conjunto de herramientas lo parte por la mitad.** Lo que
pesa son las definiciones de herramientas, no el prompt de sistema -reemplazarlo con `--system-prompt`
no baja nada frente a anadirlo con `--append-system-prompt`: 105.873 contra 99.090 acumulados-. Pero
quitar las herramientas si baja, y mucho. Misma tarea, mismo modelo, mismo system prompt, mismo esquema:

| | Sin acotar | `--tools 'Read,Grep,Glob' --strict-mcp-config` |
|---|---|---|
| Contrato (`verify-verdict`) | exit 0, PASA | exit 0, PASA |
| Preambulo acumulado | 99.090 | **32.074** |
| Coste | 0,109 $ | **0,052 $** |
| Duración | 51-86 s | **29 s** |
| Turnos | 6 | 5 |

O sea que la receta del verificador -restringir a lo que de verdad necesita para juzgar- **es a la vez
la garantía y la palanca de coste**: la mitad de dinero, un tercio del tiempo, y la incapacidad de
ejecutar pasa a ser estructural. No hay que elegir entre seguro y barato.

Y sobre el coste absoluto: **no es coste nuevo**. Los subagentes de hoy ya pagan su propio preambulo. Lo
que la arquitectura propia elimina es el coste del orquestador, que pasa a ser Python y cuesta **cero
tokens**. Esta última frase es **razonamiento, no medición**: no se puede instrumentar el consumo de un
subagente desde dentro de la sesión que lo lanza.

### Lo que obliga a cambiar el diseño

**Los permisos del implementador son el problema difícil, y hay que resolverlo antes de escribir el
orquestador.**

- Modo de permisos por defecto: **entra en barrena**. Diez turnos, 0,11 dolares, seis denegaciones y
  cero ficheros escritos.
- `--permission-mode acceptEdits` **si escribe ficheros** sin `--dangerously-skip-permissions`. Pero
  `Bash` sigue denegado, así que no puede correr los tests, y el implementador los necesita: el ciclo
  de desarrollo guiado por tests es su metodologia entera.
- **Pre-aprobar comandos por patrón no es viable.** Tres ejecuciones del mismo prompt produjeron tres
  cadenas distintas (`python -m pytest test_mod.py -v`, `pytest test_mod.py -v`, y la variante con
  `python3`). No se controla lo que teclea el agente, así que un `--allowedTools 'Bash(...)'` derivado
  de los controles declarados falla de forma intermitente, que es el peor modo de fallo posible.

De ahi que la única combinación que funciona sea **permisos amplios con aislamiento en el proceso**
(contenedor o worktree), que es exactamente lo que ya recomienda `docs/research-agent-loops.md`
-"contenedores como control principal de blast radius", y "los worktrees aislan estado de código, no de
ejecución"-. El aislamiento deja de ser una mejora del Nivel 3 y pasa a ser **requisito de la primera
versión**.

Lo que `--tools` si aporta aquí es **acotar que hay que aislar**: al implementador se le da el conjunto
mínimo que necesita para su ciclo, con lo que el aislamiento tiene que cubrir lo que `Bash` puede hacer y
no treinta herramientas más los conectores externos. Reduce el problema, no lo resuelve: una vez `Bash`
esta presente, no hay forma de acotarlo por patrón.

**`--bare` no sirve con autenticación de suscripción.** Devuelve `Not logged in` y exit 1: exige
`ANTHROPIC_API_KEY` estricta y nunca lee OAuth ni el llavero. La vía de minimizar contexto con ese flag
implica una facturación aparte.

### Dos hallazgos que no se buscaban

- **El JSON de salida trae la telemetria que faltaba**: `total_cost_usd`, `usage` con desglose de cache,
  `num_turns` y `duration_ms`. `metrics.py` deja de necesitar OpenTelemetry para el coste, y
  `--coste-tokens` deja de ser opcional.
- **`permission_denials` es una señal determinista** de que el agente intento algo que no debia. Hoy el
  repo no tiene forma de saberlo.

### Un footgun operativo

Los flags variadicos (`--tools A B C`, `--disallowedTools A B C`, `--allowedTools A B C`) **se tragan el
prompt posicional** y la invocación muere con `Input must be provided either through stdin or as a prompt
argument`. Hay que usar la forma con comas y pasar el prompt por entrada estándar. Importa más de lo que
parece porque `--tools` es el flag de la receta recomendada: el fallo no es silencioso, pero se parece a
un problema de prompt y no a uno de parseo de argumentos.

## Fuentes

- [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) — los doce factores,
  leidos completos el 2026-07-31.
- `docs/research-agent-loops.md` — aislamiento, circuit breakers y el coste impredecible; es lo que
  sostiene que el aislamiento sea requisito y no mejora.
- Las notas de diseño de entonces — la fase 2 pendiente ya nombraba *"un proceso `claude -p` por slice lanzado
  desde un script"*. La lectura de los doce factores no lo inventa: lo asciende de opción a
  arquitectura.
- `docs/maturity-map.md` — donde encaja el pipeline y por que el cluster C es el siguiente escalon.
