---
name: slice-spec
description: Crea (o valida) una spec de slices en el formato exacto que consume slice-runner. Usar cuando el usuario quiera "escribir una spec", "montar el plan de slices", "trocear una feature en slices", "slice-spec", o tenga una idea/feature y necesite convertirla en una spec ejecutable por slice-runner. Disena investigando el codigo; el dominio, la arquitectura y los contratos se preguntan siempre y del resto solo lo ambiguo que cambia lo que se construye; propone el troceo para confirmarlo y hace que otro agente refute el borrador; luego crea el issue padre (intencion, fuentes de convencion y controles) con una subissue por slice (titulo con identificador y nombre, intencion, criterios de aceptacion, senal y etiqueta de estado). Modo `validate` para revisar una spec existente contra el contrato. Cierra proponiendo que slices pueden correr en paralelo y, si se confirma, monta un worktree por slice y lanza sus runs. No implementa codigo: produce la spec que slice-runner luego ejecuta.
---

# Slice Spec

STARTER_CHARACTER = [slice-spec]

Emite `[slice-spec]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Skill que produce la **spec** que `slice-runner` consume, en su formato exacto. El diseno lo lleva
**investigando el repo y preguntando solo lo que la persona tiene que decidir** (`references/diseno.md`),
y despues aplica el **contrato de formato** (los nombres de slice, los criterios de aceptacion, las lineas
que `slice-runner` sabe parsear). Es el `check-alignment` + `text-native` del flujo: la spec es el
artefacto compartido entre humano y agente, y **vive en GitHub**: una feature = **un issue padre**
mas **una subissue por slice**.

Par natural: `/slice-spec` crea el issue padre y sus subissues, `uv run slice-runner run <N> --repo
<org>/<repo> --base master` las ejecuta, una invocacion por slice.

Dos modos:

- **Autoria (por defecto):** diseno -> troceo confirmado -> crea el issue padre y una subissue por slice, bien formadas.
- **`validate`:** revisa una spec existente contra el contrato -el issue padre `#N` con sus subissues,
  o el borrador de antes de crearlos- y reporta (o corrige) desviaciones con su regla y su ubicacion.

## Principios

- **No implementa.** No escribe codigo ni tests; produce la spec. El estado terminal es una spec
  valida, no un plan de `writing-plans` ni una PR.
- **El diseno se investiga y se interroga, no se aprueba.** Un diseno que se aprueba deja decisiones
  sin tomar, y cada una la toma el implementador sin que nadie la vea, o reaparece como un hallazgo del
  juez con la vuelta ya pagada. Pero preguntarlo todo tampoco sirve: la persona acaba contestando a
  destajo casos que no se van a dar. Por eso la profundidad la pone el agente -los hechos los buscan
  subagentes, nunca se preguntan-; el dominio, la arquitectura y los contratos se preguntan siempre,
  en un bloque de arquitectura; del resto a la persona solo le llega lo ambiguo que cambia lo que se
  construye, y lo demas lo decide el agente y lo lista para que se vete; y alguien que no diseno intenta
  refutar el borrador (`references/diseno.md`). No hay `writing-plans`: la spec ES el plan que consume slice-runner.
- **Formato es contrato.** La spec la parsea `slice-runner` sin ambiguedad: el cuerpo del padre, el
  titulo y el cuerpo de cada subissue, y su etiqueta de estado. Si no cumple el contrato de abajo, no
  esta terminada.
- **Cada slice tiene nombre.** `name` kebab-case, estable, determinista: alimenta rama y scope de
  commit en slice-runner. Sin nombre no hay spec bien formada.
- **Guia el corte, no lo delega.** El troceo lo lleva esta skill cargando su cerebro de slicing
  (`references/slicing.md`): walking skeleton, heuristica ordenada, hamburger como motor de
  composicion, calibrador de tamano y validacion del corte. La skill es la **fuente de verdad** del
  slicing; `hamburger-method`/`story-splitting` son profundizacion opcional, no el motor.
- **Slices verticales y pequenas.** Cada slice es una rebanada entregable de punta a punta con
  criterios de aceptacion propios, no una capa tecnica suelta.
- **La intencion es parte de la spec, y es lo primero que se lee.** El issue abre con una seccion
  `## Intencion` (que esta mal hoy, o que no se puede hacer hoy, a quien le pasa y como se nota) y
  cada slice declara su linea `INTENCION:` (que deja de estar mal cuando esa slice entra). No es
  decoracion: es lo que acaba en el cuerpo de cada pull request, en lugar de un resumen del codigo
  -que el diff ya cuenta mejor-. **Vara: el coste de no hacerlo.** Si borras la slice, ¿que queda
  roto o imposible? Si no puedes nombrarlo, la linea es relleno y hay que reescribirla:
  `INTENCION: hoy se pueden prestar mas ejemplares de los que hay y el inventario queda en negativo
  sin que nadie se entere` cumple la vara; `INTENCION: mejorar la validacion del dominio` no (borrala y no queda
  nada roto que puedas nombrar). A diferencia de `SENAL:`, **no hay figura de exencion**: una slice
  sin por que no deberia existir. Las slices sin efecto observable en produccion (refactor, value
  object interno) tambien tienen intencion; su coste es interno, pero se puede nombrar.
- **Criterios de aceptacion obligatorios y falsables.** Sin ellos no hay control de verificacion en
  slice-runner: toda slice declara criterios concretos. **Vara de falsabilidad:** un criterio vale
  si puedes nombrar el **cambio de produccion que lo haria fallar**; si no puedes nombrarlo, es
  prosa y hay que reescribirlo. Es la contraparte upstream de "los tests son ciudadanos de primera
  categoria" de slice-runner: su verificador bloquea con severidad alta el mapeo criterio↔test, y
  ese check solo tiene con que medir si el criterio es falsable.
- **La observabilidad es parte del corte, no un extra.** Toda slice que cambia comportamiento
  observable en produccion declara su linea `SENAL:`: **como se comprueba viva**. Es la contraparte
  post-deploy de los criterios de aceptacion — estos los verifica un test antes de mergear, la senal
  la comprueba quien despliega, despues— y la misma vara de falsabilidad aplicada al otro extremo:
  *nombra la senal que cambiaria si esto se rompe vivo*. Si no puedes nombrarla, la slice no es
  observable, y eso se arregla **en el slicing**, no en el incidente. Las exentas (refactor puro, VO
  interno, migracion sin efecto visible) lo declaran con motivo: `SENAL: exenta - <motivo>`;
  ausencia silenciosa no es exencion. El detalle vive en `references/observabilidad.md` (escalera
  para decidir si hay que instrumentar o la senal ya existe, stack concreto, redaccion de la linea).
- **Alertas y paneles son slices propias, en su repo.** Una alerta o un panel no van nunca en la PR de
  la metrica que consumen (repos distintos ⇒ PRs distintas), y el orden es forzoso: primero la slice
  que emite la serie, luego la alerta, luego el panel. Se declaran con `REPO:` en su linea.
- **Investiga antes de cortar.** El troceo se hace sobre lo que ya hay, no sobre un repo imaginario:
  antes del paso 2 se busca **que se intento antes** y **que existe ya que se pueda reutilizar**, y lo
  confirmado viaja en la seccion `## Lo que ya existe` del padre. Los dos
  fallos que esto corrige son reales: una slice que iba a implementar algo que ningun consumidor leia,
  y otra que tradujo el vocabulario de un script que una tercera estaba jubilando. **Vara: un hallazgo
  es una ruta o un numero, no una impresion.**
- **Declara las fuentes de convencion.** La spec incluye una seccion `## Fuentes de convencion` con
  **punteros** (no contenido) a la vara de medir del repo: docs de convencion y skills de proyecto.
  slice-runner las lee para que implementador y verificador midan contra las convenciones **reales**
  del repo, no contra defaults genericos ni contra como quedo una slice anterior. No se asumen rutas
  fijas: se **descubren** por repo (paso 3) y las **confirma la persona**. Sin esta seccion,
  slice-runner para y no ejecuta con la vara vacia (evita el `silent-misalignment` de trabajar sin
  criterio y no avisar).
- **Declara los controles.** Si las fuentes son la vara, la seccion `## Controles` son **los comandos
  con los que se mide**: `lint`, `types`, `tests` y lo que el repo tenga. Tambien se descubren y se
  confirman (paso 3b), y por el mismo motivo: antes los deducia `slice-runner` leyendo el `Makefile`
  al empezar cada slice, lo que le metia el toolchain del repo en el contexto que debe durar todo el
  run y no dejaba rastro que nadie pudiera revisar. Declarados aqui, la vara es **texto publico** que
  ninguna slice puede debilitar en privado.
- **La spec vive en GitHub, repartida por slice.** `slice-spec` crea el issue padre de la feature y
  una subissue por slice: es la fuente de verdad duradera del estado, no un fichero en el repo. No la
  guardes en `docs/` ni la comitees. El reparto es deliberado: **etiquetas para lo que se consulta,
  cuerpo para lo que se reanuda**, asi que una transicion de estado es una escritura de etiqueta y
  nadie reescribe el documento de nadie. Su coste es que la spec deja de leerse de un tiron, y no se paga
  volcandola por el terminal: el cuerpo de las subissues esta escrito para que lo parsee un programa, y
  de las subissues la persona revisa antes de crear solo el troceo (paso 2d); el detalle lo lee en GitHub. **Tampoco**
  se paga repitiendo las slices en el cuerpo del padre, que seria estado duplicado que deriva.
- **Trocear termina cuando el trabajo esta lanzado, no cuando el issue esta escrito.** Quien acaba de
  cortar es quien mejor sabe que va a tocar cada slice, asi que el reparto en paralelo -que puede ir
  con que, y que no- se propone aqui (paso 7) y, confirmado, se lanza aqui: un run por slice, cada uno en su
  worktree. Dejarlo para despues obliga a reconstruir a ojo lo que en este momento se sabe. **Lo que no se
  hace es prometer que las slices son disjuntas**: se declara el solape que se espera, porque la
  version comoda ya ha fallado dos veces y una fusion avisada no cuesta nada.

## Contrato de formato (lo que el programa lee)

Una feature = **un issue padre** + **una subissue por slice**. Un solo formato, sin variantes.

| Donde | Que lleva |
|---|---|
| Issue padre | `## Intencion`, `## Lo que ya existe`, `## Decisiones`, `## Fuentes de convencion` y `## Controles`, los dos ultimos por repo, mas `## Historia de usuario` si la feature tiene una -y entonces tambien la clave delante de su titulo y la etiqueta `origen:<clave>`-. Las slices son sus subissues, y la barra de progreso la calcula GitHub |
| Titulo de la subissue | `slice-NN (name): titulo`, con la clave de la historia de usuario delante si el padre la declara; de ahi sale el orden de ejecucion, y de `name` sale la rama (con la clave delante del numero cuando la hay: `slice/HU-123-NN-name`) y el scope del commit |
| Cuerpo de la subissue | Las lineas de la slice, cada grupo bajo su encabezado: `REPO:`, `INTENCION:`, `DECISION:`, `ACEPTACION:`, `SENAL:`, `EXCLUYE:`, `SUSTITUYE:`, y `DISENO:` solo si la slice construye algo visual |
| Etiqueta de la subissue | El estado macro, que arranca en `estado:pendiente`, mas `origen:<clave>` si el padre declara historia de usuario |

### El issue padre

```markdown
## Intencion
Hoy un ajuste del inventario de ejemplares se hace a mano en la consola y no queda rastro de quien lo
hizo ni de por que. Cuando un lector reserva un libro que figura disponible y no aparece, la sucursal no
puede reconstruir que paso y acaba abriendo un caso a soporte, que tampoco tiene donde mirar. Y como
nada valida la cantidad, un ajuste negativo entra sin que nadie lo frene y deja el inventario en
negativo hasta que alguien lo nota.

## Lo que ya existe
- pieza: src/catalogo/domain/inventario_repository.py - guarda y lee los ejemplares por isbn; esta
  slice usa esa lectura para decidir si el ajuste deja el inventario en negativo, no introduce otro puerto
- precedente: #88 - se intento con un job nocturno y se revirtio porque no daba trazabilidad del quien
- acopla: `AjustarInventario` ya emite el evento; el ajuste manual se engancha ahi, no en el endpoint

## Decisiones
- el ajuste se registra en una tabla propia y no en el log de auditoria, porque soporte necesita consultarlo por isbn
- la cantidad negativa se rechaza en el caso de uso y no en el endpoint, para que valga tambien desde el evento

## Fuentes de convencion
- doc: CLAUDE.md
- skill: .claude/skills/nuevo-caso-de-uso

### tu-org/infra-alertas
- doc: templates/CLAUDE.md

## Controles
- lint: make linting
- types: make check-types
- tests: make test

### tu-org/infra-alertas
- ninguno: la integracion continua de ese repo no valida en PR

<!-- slice-runner:workspace 3f2b8c1e-5a7d-4e90-9b6a-1c2d3e4f5a6b -->
```

### Una subissue por slice

Cada slice es una subissue **hija de ese padre**, con su etiqueta de estado desde que nace:

- **Titulo**: `slice-03 (alerta-inventario-negativo): avisa cuando el inventario queda en negativo`. Delante va
  `slice-NN`, de donde sale el orden de ejecucion -no del orden en que la interfaz de programacion
  devuelva las subissues-; entre parentesis, el `name` en kebab-case, de donde salen la rama
  `slice/NN-name` y el scope del commit. Si el padre declaro `## Historia de usuario`, la clave va
  delante del `slice-NN` en el titulo y tambien delante del numero en la rama: `slice/HU-123-NN-name`.
- **Etiqueta**: `estado:pendiente`, el estado macro inicial, mas `origen:<clave>` si el padre
  declaro `## Historia de usuario` (ver Reglas duras, mas abajo).
- **Cuerpo**: las lineas de la slice, cada grupo bajo su encabezado. El bloque
  `<!-- slice-runner:estado ... -->` es propiedad de la maquina -lo escribe `slice-runner` para poder
  reanudar- y aqui no se escribe nunca.

El ejemplo es el caso cross-repo, que es el que mas cosas exige: una slice que se implementa en el repo
del padre no lleva la seccion `## Repositorio`.

```markdown
## Repositorio
REPO: tu-org/infra-alertas

## Por qué
INTENCION: hoy el inventario se queda en negativo y nadie se entera hasta que una sucursal llama a soporte

## Criterios de aceptación
ACEPTACION: la alerta dispara con inventario negativo sostenido 10m y no con un negativo aislado
ACEPTACION: la alerta sale con severidad critical y apunta al runbook del inventario

## Fuera de alcance
EXCLUYE: el panel de Grafana que visualiza esta misma serie va en su propia slice, detras de esta

## Qué sustituye
SUSTITUYE: no

## Decisiones
DECISION: la alerta mira el minimo en ventana de 10m y no el valor instantaneo, para no avisar por un negativo aislado

## Señal en producción
SENAL: prometheus min_over_time(ejemplares_disponibles[10m]) < 0 dispara la alerta en 15m post-deploy
```

### Reglas duras

- El padre abre con `## Intencion`: el problema de la feature entera, que esta mal hoy y como se nota.
  Es lo primero que lee una persona al abrirlo, y lo que `slice-runner` reutiliza en el cuerpo de cada
  pull request. Sin ella la spec no esta terminada.
- El padre lleva `## Decisiones` con lineas `- <decision>`: **lo que la persona decidio de diseno al
  disenar la feature y que el implementador no tiene que adivinar** -que se elige entre dos caminos
  razonables y por que-. Es la decision, no un criterio de aceptacion disfrazado ni un detalle del
  codigo. Si de verdad no hay ninguna, la seccion lleva una sola linea `- ninguna: <motivo>`; **vacia
  no vale**, y un padre sin ninguna linea para el run en la comprobacion previa con `missing-decisions`.
- El padre puede llevar `## Diseno`, **solo cuando la feature tiene una maqueta**: un `### <nombre>` por
  diseno -dentro de esta seccion `###` es el nombre del diseno y nunca un repo-, y debajo un `<details>`
  cuyo `<summary>` lleva el enlace al artefacto y, dentro, el HTML de la variante elegida en **un bloque
  de codigo**. `slice-runner` mete en el prompt del implementador y en el del juez el contenido del
  **primer bloque de codigo** de cada diseno que una slice cita, tal cual y sin destilar; el `<details>`,
  el `<summary>` y el enlace son para la persona y no viajan. Cuenta dentro del mismo tope de caracteres
  que las fuentes de convencion. Un diseno que ninguna slice cita no viaja a nadie.
- Una slice que construye algo visual lleva una linea `DISENO: <nombre>` por cada diseno que cita, con el
  nombre **exacto** de un `### <nombre>` de `## Diseno` del padre. Es opcional, y el ejemplo de
  arriba no la escribe a proposito: una slice sin ninguna no recibe HTML aunque el padre declare
  disenos. **Un `DISENO:` que nombra un diseno que el padre no declara para el run en la comprobacion
  previa con `unknown-design`**, sin marcar la subissue en curso.
- El padre lleva `## Lo que ya existe` con lineas `- pieza: <ruta> - <que hace hoy>`,
  `- precedente: #<numero> - <que le paso>` o `- acopla: <sitio> - <como>`. **Cada linea cita una ruta
  o un numero**: un hallazgo que no se puede ir a comprobar es una impresion y no entra. **Y una linea
  `- pieza:` dice que hace hoy esa pieza, no solo que existe**: el puntero ya lo dio el paso 1b, y
  nombrar una ruta que existe deja de cumplir la vara. Si de verdad no hay nada, la seccion lleva una
  sola linea `- nada: <motivo>`; **vacia no vale**, por lo mismo que `SENAL:` distingue exenta de
  ausente.
- El padre lleva `## Fuentes de convencion` con lineas `- doc: <ruta>` o `- skill: <ruta>`: punteros
  confirmados a la vara de medir del repo (los escribe el paso 3; slice-runner los exige). Punteros,
  nunca el contenido de la convencion.
- **Cada ruta es un fichero, nunca un directorio.** `slice-runner` **lee el contenido** de cada fuente
  y lo mete en el prompt de los tres agentes, asi que `- doc: docs/conventions/` no es un puntero mas
  corto: es una fuente que no se puede leer, y para el run en los prechecks. Y listar la carpeta
  tampoco valdria: meteria en el prompt lo que **no** es la vara del codigo -el flujo de trabajo de una
  persona, la convencion de como se redacta una convencion- y haria que anadir un fichero ahi cambiase
  en silencio lo que ven los tres agentes. Se listan los ficheros, uno por linea.
- **Las fuentes son por repo.** Las lineas antes de cualquier `### <org>/<repo>` son las del repo del
  padre; cada subseccion `###` declara la vara de un repo destino. Si una slice lleva `REPO:`, su repo
  **tiene que** tener su subseccion: medir una alerta del repo de manifiestos con las convenciones del
  repo de la app es exactamente la desviacion silenciosa que esta seccion evita.
- El padre lleva `## Controles` con lineas `- <nombre>: <comando>`: los comandos deterministas con los
  que se mide el repo (los escribe el paso 3b; slice-runner los exige y **no deduce nada** en tiempo de
  run). Los nombres son libres -`lint`, `types`, `tests`, o `schema` en un repo de manifiestos-, pero el
  comando tiene que ser **exacto y ejecutable tal cual**, porque nadie lo va a interpretar: se ejecuta.
- **Los controles tambien son por repo**, con la misma forma que las fuentes y por la misma razon:
  correr `make test` de la app contra el repo de manifiestos no valida nada. Un repo sin controles
  reales se declara con la linea reservada `- ninguno: <motivo>`, que **no es un control llamado
  `ninguno`**: es la exencion, y lo que la sigue es el motivo, no un comando -si acabara ejecutandose,
  alguien pasaria una frase en castellano a un shell-. Vacio y eximido no son lo mismo: vacio hace que
  `slice-runner` pare, e inventarse un control finge una garantia que no existe. Y la exencion no admite
  controles al lado: "no hay controles" y "hay estos" no pueden ser ciertas a la vez.
- **El padre no repite las slices.** Su detalle vive en cada subissue; copiarlo arriba es estado
  duplicado que deriva en cuanto una slice cambia.
- **Una subissue por slice, y creada como hija del padre** (`gh issue create --parent`). El parentesco
  no es cosmetico: `slice-runner` busca las slices de una feature con `parent-issue:<org>/<repo>#<N>`,
  asi que una subissue creada sin `--parent` es una slice que no existe para el run.
- **El titulo es `slice-NN (name): titulo`, con la clave de la historia de usuario delante cuando el
  padre la declara** (`HU-123 slice-NN (name): titulo`; el formato completo de esa clave esta un poco
  mas abajo). `NN` = orden de dos digitos, y es lo que ordena las slices; `name` = kebab-case unico
  dentro de la feature, y es lo que deriva la rama y el scope del commit. Un titulo cuyo `slice-NN` -
  precedido o no de esa clave- no aparece donde el programa lo espera no se puede leer y para el run.
- **El parentesis lleva el `name` y nada mas.** Nada de un type de conventional commit delante: el
  programa se lleva el parentesis entero como nombre, asi que un `(refactor: extraer-repo)` le pide a
  git una rama llamada `slice/03-refactor: extraer-repo`, que no es un nombre de rama valido, y el run
  muere **despues** de haber marcado la subissue en curso y pagado la llamada. El type del commit lo
  elige el agente al redactarlo -sabe conventional commits-, y su unico control determinista es la
  higiene del diff que aplica el programa al stagear, asi que declararlo aqui no alimentaba nada.
- **El estado macro es una etiqueta, nunca una marca en el texto.** Toda subissue nace con
  `estado:pendiente` y `slice-runner` la mueve escribiendo etiquetas (`estado:en-curso`,
  `estado:esperando-merge`, `bloqueada:controles`, `abortada:presupuesto`...); mergeada es GitHub
  cerrando la subissue al fusionar su pull request. Un segundo sitio donde escribir el estado es un
  sitio donde puede desmentir al primero, y nada lee ese.
- **Si la feature tiene una historia de usuario, su clave va en una seccion propia del padre y
  delante del `slice-NN` en el titulo de cada subissue.** La clave son mayusculas y digitos, un guion
  y uno o mas digitos: una letra mayuscula, cero o mas letras mayusculas o digitos, `-`, uno o mas
  digitos (`HU-123`, `JIRA2-10`). Una clave en minusculas, con guion bajo, o sin el numero final no
  tiene esa forma y `slice-runner` no la lee. El padre la declara con:

  ```markdown
  ## Historia de usuario
  HU-123
  ```

  y esa clave se antepone al titulo de cada subissue de la feature, como primera palabra y separada
  de `slice-NN` por un espacio: `HU-123 slice-04 (nombre): titulo`. Su ausencia dice que la feature
  no tiene historia de usuario asociada, y el titulo se queda exactamente como hoy: sin esa palabra
  delante.

  **Y tambien delante del titulo del padre** (`HU-123 <feature>`), por el mismo motivo por el que va
  en el de las subissues: en el listado de issues no se abre nada, y un padre que no la lleva es el
  unico issue de la feature que no dice a que historia pertenece. El programa **no** parsea el titulo
  del padre -solo el de las subissues-, asi que esta mitad es para quien mira, no para quien ejecuta.
- **La etiqueta de historia de usuario lleva la clave dentro, una por historia.** Cuando el padre
  declara `## Historia de usuario`, la subissue nace ademas con `origen:HU-123` (el patron es
  `origen:<clave>`, y lo que va detras de los dos puntos es siempre la clave de la historia de usuario:
  el prefijo dice **de donde viene el trabajo**, no en que estado esta), escrita en la misma llamada de
  creacion junto a `estado:pendiente`. No entra
  en el vocabulario cerrado de `IssueLabel` -que asume una sola etiqueta de estado por issue-: es
  una etiqueta mas, y filtrar por ella en GitHub aisla exactamente las subissues de esa historia, no
  todas las que tengan alguna.

  **El padre la lleva tambien**, y no es redundante: la etiqueta es la unica forma de pedirle a GitHub
  "todo lo de esta historia" de una vez, y sin ella el filtro devuelve las slices pero deja fuera el
  issue donde viven la intencion, las fuentes y los controles. El padre no lleva etiqueta de estado
  -el estado es de cada slice-, asi que `origen:<clave>` es la unica que tiene.
- **El cuerpo agrupa sus lineas bajo encabezados, en el orden del ejemplo**: `## Repositorio`
  (`REPO:`, solo si la slice va en otro repo), `## Por qué` (`INTENCION:`), `## Criterios de aceptación`
  (`ACEPTACION:`), `## Fuera de alcance` (`EXCLUYE:`), `## Qué sustituye` (`SUSTITUYE:`), `## Decisiones`
  (`DECISION:`, y `DISENO:` si lo hay) y `## Señal en producción` (`SENAL:`). Los encabezados son para
  quien revisa la subissue en GitHub; el programa los ignora y solo lee las lineas, asi que **cada linea
  empieza por su etiqueta**, sin guion ni negrita delante: con ellos el programa no la ve y el campo llega
  vacio sin que nada falle.
- El cuerpo lleva una linea `INTENCION:` con el coste de no hacer la slice: que esta mal hoy y deja de
  estarlo cuando entra. Va **antes** de los `ACEPTACION:` (primero el por que, luego lo que se comprueba
  antes de fusionar, luego lo que se comprueba vivo). Obligatoria siempre, sin exencion posible.
- El cuerpo lleva una o mas lineas `ACEPTACION:` con criterios concretos (y donde viven los tests si
  aplica). Las **restricciones duras** (p. ej. "no toca infra directamente") se expresan como un
  criterio comprobable mas.
- **Cada criterio debe ser falsable**: tiene que poder nombrarse el cambio de produccion que lo haria
  fallar. `ACEPTACION: rechaza cantidades negativas con ValueError` lo es (borra la validacion y falla);
  `ACEPTACION: el flujo funciona correctamente` no lo es (nada lo puede refutar). Un criterio no
  falsable deja al verificador de slice-runner sin nada contra lo que mapear el test, asi que no cumple
  el contrato.
- **Donde vive una pieza es una decision, no un criterio.** Capa, puerto, modulo o fichero de una pieza
  nueva se deciden en el paso 1 y se escriben como `DECISION:` de la slice
  que la introduce, o en `## Decisiones` del padre si afectan a varias. Los criterios de aceptacion
  hablan de lo que el codigo hace; la forma la mide el verificador contra esas decisiones y contra las
  fuentes de convencion del repo.
- **Y cada criterio se le pide a quien puede cumplirlo, y se escribe contra lo que el verificador
  recibe.** Son dos filtros y hay que pasar los dos.

  El implementador no toca `git` -ni commitea, ni stagea, ni cambia de rama, ni redacta mensajes de
  commit- y no compone el cuerpo de la pull request: lo que devuelve es codigo, tests y su informe. Un
  criterio que pida algo fuera de eso es **invalido aunque sea falsable**, porque nadie en el pipeline
  puede cumplirlo. `ACEPTACION: la retirada de los tests va en un segundo commit` hay que reescribirla
  (el reparto en commits lo decide el programa); `ACEPTACION: el cuerpo de la pull request nombra el
  test que cubre cada uno retirado` tambien (el cuerpo se compone solo).

  **Y el verificador solo recibe el diff, la spec y las fuentes de convencion: no recibe el informe del
  implementador.** Asi que un criterio que apunte al informe es **inverificable por quien tiene que
  medirlo**, aunque el implementador si pueda cumplirlo. Eso no es una vara: es pedirle al juez un
  veredicto sobre algo que no ve, y lo que devuelve es un hallazgo en cada ronda -medido: sale en tres
  slices seguidas, y el juez acabo etiquetandolo "sin veredicto por falta de dato"-.

  **La reescritura es apuntar al diff, que es lo que el juez si tiene delante.** `ACEPTACION: por cada
  test retirado, el informe nombra el del caso de uso que lo cubre` hay que reescribirla como
  `ACEPTACION: cada comportamiento que cubria un test retirado lo cubre otro test que esta en el diff`:
  dice lo mismo, se comprueba leyendo el diff, y el implementador lo declara igualmente en su informe
  porque es donde declara lo que toca.
- **Y un criterio que pide una cantidad dice cuantas.** Cuando el comportamiento que pide **solo se
  distingue con mas de una ocurrencia**, el numero es parte del criterio y no un detalle del test.

  `ACEPTACION: cada X que ocurra deja su propio Y, y hay test` se cumple con un test de una sola X
  -que produce un solo Y, y eso es lo que el programa ya hacia- y tambien con uno de dos. Quien
  implementa pinea la lectura barata y quien juzga exige la otra, **los dos cumpliendo el criterio tal
  como esta escrito**, asi que ninguno puede ceder citandolo y el desacuerdo no sale hasta que el
  presupuesto esta gastado. Paso de verdad, y se llevo un run entero. Hay que reescribirla como
  `ACEPTACION: dos X que ocurran dejan DOS Y, y hay test que assertea exactamente ese numero`.

  **La pregunta que lo caza: *¿el caso de uno se distingue de lo que el programa ya hacia?*** Cuando la
  respuesta es que no, el criterio dice el numero. Y cuando si se distingue -"cada Y stagea solo lo
  declarado" falla con uno solo mal stageado-, el cuantificador no necesita numero: la vara no es la
  palabra, es si el caso de uno discrimina.
- **Una slice que traslada logica declara que se retira de donde estaba.** Cuando el trabajo es mover
  algo de A a B -un paso que se va a su caso de uso, una regla que baja al dominio-, el criterio sobre
  tests dice **que sale de A**, no solo que A sigue verde. "Los tests de A siguen verdes sin tocarlos"
  es la red que prueba que el comportamiento no cambio **mientras** se traslada, y es buena; pero si es
  lo unico que se pide, dejar en A la cobertura que ahora tambien vive en B es la respuesta correcta
  segun la vara, y la duplicidad se queda. Se piden las dos cosas: la red durante el traslado y la
  retirada despues.
- **Y al retirarla, un test que cubria dos mitades no se retira entero.** Si el test que sobra
  comprobaba ademas algo que la pieza nueva no puede ver -la transicion que produce, la etiqueta que se
  escribe, lo que cruza invocaciones-, esa mitad se queda fijada donde estaba. `ACEPTACION: se retira de
  A lo que solo ejercita <lo trasladado>, y lo que ademas fijaba una transicion se queda` cumple la
  vara; `ACEPTACION: se retiran los tests duplicados` no, porque no dice quien decide que es duplicado.
- El cuerpo lleva al menos una linea `DECISION:` con **una decision de diseno que afecta a esta slice y
  que el implementador no tiene que adivinar**. Si de verdad no hay ninguna, se declara con
  `DECISION: ninguna - <motivo>`, igual que `EXCLUYE: nada - <motivo>`; **un cuerpo sin ninguna linea
  para el run en la comprobacion previa con `missing-decisions`**.
- El cuerpo lleva una linea `SENAL:` con **como se comprueba viva en produccion** (formato:
  `<fuente> <serie/expresion>; <assert vivo con ventana>`), o
  `SENAL: exenta - <motivo>`. Es obligatoria cuando la slice cambia comportamiento observable en prod.
  **La senal tambien es falsable**: `SENAL: se monitoriza con Grafana` no vale (no nombra serie,
  ventana ni assert); `SENAL: prometheus rate(ejemplares_ajustados_total[5m]) > 0 en 10m
  post-deploy` si. Si la senal hay que **construirla**, su emision entra ademas como criterio
  de aceptacion normal (el test de emision): la emision se verifica pre-merge, el valor vivo post-deploy.
- El cuerpo lleva una linea `EXCLUYE:` con **lo que esta slice deja fuera de su alcance a proposito**:
  andamiaje de una slice futura ya prevista, no algo que falte. Es obligatoria siempre, sin ausencia
  silenciosa: si de verdad no hay nada que excluir, se declara con `EXCLUYE: nada - <motivo>`, igual
  que `SENAL: exenta - <motivo>`. Es una **prohibicion que viaja a los dos agentes**: el implementador
  no construye lo que nombra, y el verificador bloquea si aparece en el diff, citando la linea en vez de
  tener que argumentar que sobra.
- El cuerpo lleva una linea `SUSTITUYE:` que dice **si el diff sustituye algo que ya esta funcionando**.
  Es obligatoria siempre y **sin figura de exencion**: a diferencia de `EXCLUYE:` y de `SENAL:`, aqui no
  hay `nada`/`exenta` posible, porque la pregunta siempre tiene una respuesta, aunque sea que no.

  **La segunda mitad depende de como se distribuye el sujeto, y confundirlo es lo que hace que la linea
  se rellene con prosa.** Hay dos formas y hay que elegir la del repo destino:

  - **Un servicio desplegado** -algo que corre en produccion y atiende trafico-: `SUSTITUYE: si - <que
    sustituye>; <como se vuelve atras sin redeploy>`. Ahi el mecanismo existe -un flag, expand-contract-
    y nombrarlo es lo que deja al verificador algo que exigir en el diff.
  - **Un programa que se instala** -una linea de comandos, una libreria, un script-: volver atras **es**
    reinstalar la version anterior, asi que escribirlo no informa de nada. La pregunta que si muerde
    aqui es otra: `SUSTITUYE: si - <que deja ilegible o inservible de lo que ya esta escrito>; <que pasa
    con lo que ya existe>`. Ficheros, filas de un almacen durable, estado persistido, etiquetas.

  **Medido, y por eso esta escrito asi:** con la forma del servicio aplicada a un programa que se
  instala, la linea no cazo ni una de las tres roturas de generacion reales de una feature entera -un
  almacen que dejo de leerse, otro que impedia cerrar cualquier slice, un campo renombrado- y en cambio
  produjo tres hallazgos sobre si misma, porque prometia un rollback que no existia. Cero hallazgos de
  severidad alta en 445: no bloqueo nunca. La linea no fallaba por estar mal redactada, fallaba por
  preguntar lo que en ese repo no aplica.
- Linea `REPO: <org>/<repo>` cuando la slice se implementa en otro repo (alerta, panel). Ausente = el
  repo del padre. Toda slice con `REPO:` exige la subseccion de fuentes **y de controles** de su repo.
- Una feature de **una sola slice** = un padre con una sola subissue.

## El worktree de una slice

Todo run vive en un worktree, y **lo monta el programa**: nadie lo teclea ni lo coloca. El run se
lanza desde la raiz del clon -o con `--repo-root <ruta>`- y `slice-runner run` deriva la ruta de la
identidad de la slice: `<raiz-del-repo>/.worktrees/<NN-name>`, del mismo sitio de donde sale la rama
`slice/NN-name`, y la deja lista antes de entender nada. Tambien escribe `/.worktrees/` en
`.git/info/exclude` del clon principal -el que git dice por `git rev-parse --git-common-dir`-, asi que
el directorio no sale como no seguido ni obliga a tocar el `.gitignore` de nadie.

Las tres condiciones que fallan en silencio -bajo la raiz del repo, o Docker no lo ve; con punto
delante, o los controles recogen las copias de los tests; ignorado, porque git no lo hace solo- las
cumple el programa por construccion. Las mediciones que las sostienen estan en las pull requests que las introdujeron,
seccion "El worktree del programa".

**Lo que hace segun lo que encuentra**, clasificando por la rama que tiene tomada cada arbol y no por
su ruta:

- nada montado: crea la rama desde `origin/<base>` y el worktree;
- la rama existe y no tiene worktree: monta uno sobre ella;
- el worktree ya esta en su rama: no toca nada;
- el worktree esta registrado pero su directorio se borro a mano: lo sanea y monta;
- la rama la tiene otro worktree, o el arbol esta en otra rama: **cierra el run** con la etiqueta
  `bloqueada:worktree` y dice en que ruta esta el conflicto. Se libera esa ruta o esa rama y se
  reabre con `slice-runner retry <subissue> --repo <org>/<repo> <instruccion>` y reinvoca.

**`--worktree <ruta>` sigue aceptandose** para un arbol que alguien monto a mano, y manda sobre derivar
uno. Ese arbol tiene que colgar del mismo clon que `--repo-root`: si no, el run cierra en
`bloqueada:worktree` en vez de montar nada en silencio.

**Como se retira, y por que no a ciegas.** El programa commitea **al final de cada vuelta que deja sus
controles en verde**, no solo al entregar, asi que un run bloqueado o abortado puede llevar ya varios
commits propios en su rama sin que eso signifique que nada se perderia al borrar el worktree: esos
commits siguen viviendo solo en local hasta que la rama llega a la base. Antes de retirar, comprueba
**las dos condiciones**, no las supongas:

```bash
git -C <ruta-del-worktree> status --porcelain          # vacio: no hay nada sin commitear
git merge-base --is-ancestor <rama-de-la-slice> origin/<base>   # exito: nada existe solo en local
```

Con las dos cumplidas:

```bash
git worktree remove <ruta-del-worktree>
git branch -d <rama-de-la-slice>
```

Si falla cualquiera de las dos, o no se puede comprobar, **el arbol se queda** y el comentario de cierre
y la fila de metricas dicen en que ruta y por que. El programa retira solo al cerrar un run fusionado o
abortado sin haber tocado codigo; un run bloqueado conserva su arbol para reanudar. Un arbol que sobra de
un run anterior no se reutiliza ni se pisa: la invocacion siguiente cierra en
`bloqueada:worktree` y dice el comando para quitarlo a mano (`git worktree remove <ruta>`).

## Steps — modo autoria (por defecto)

0. **Descubre las fuentes de convencion y los controles del repo del padre, antes de la primera
   pregunta (`offload-deterministic`).** Corre los dos helpers deterministas sobre el repo del padre
   (`slice-runner discover-conventions <repo>` y
   `slice-runner discover-controls <repo>`) y tenlo delante
   durante el diseno -la persona lo confirma en los pasos 3 y 3b-: el diseno pregunta nombres de ficheros y clases y
   estrategia de tests solo si esas fuentes no los cubren, y no se sabe cuales cubren hasta haberlas
   visto. Los pasos 3 y 3b describen como se juzga y se confirma cada uno.
1. **Disena investigando primero y preguntando solo lo que importa (`check-alignment` + `cast-wide`).**
   Carga `references/diseno.md`. Lanza la investigacion del paso 1b antes de la primera pregunta, y
   pregunta primero el bloque de arquitectura -dominio, arquitectura y contratos con sus firmas, sin pasar
   por los filtros-. Del resto pregunta a la persona solo lo que pasa sus dos filtros: **ambiguo de
   verdad** y que **cambia lo que se construye**. Lo demas lo decides tu y lo apuntas para el paso 1c.
   **En cuanto el diseno decide que hay trabajo en otro repo**, corre el descubrimiento de ese repo
   (pasos 3 y 3b) antes de decidir sus contratos: sin su vara no se sabe que decisiones le quedan a la
   persona. Sigue hasta que el bloque de arquitectura este contestado o cerrado con su motivo y no quede
   abierta ninguna pregunta que pase los filtros, y cierra con el paso 1c.
1b. **Investiga el repo antes de preguntar, con subagentes en paralelo
   (`check-alignment` + `focused-agent`).** Trocear sin mirar que hay ya produce slices que construyen lo que existe, que
   traducen lo que otra esta jubilando, o que implementan algo que ningun consumidor lee. Lanza la
   busqueda en subagentes en paralelo, uno por area y como mucho cuatro, con los terminos del concepto que
   vas a trocear, y que contesten estas preguntas **con punteros, no con prosa**:

   - **¿Que hay ya que esto necesite?** Busca en el arbol quien nombra el concepto. Vale una ruta que
     existe; no vale "el repo ya tiene puertos".
   - **¿Se intento antes?** Mira las pull requests mergeadas y las issues cerradas
     (`gh pr list --state merged --search ...`, `gh issue list --state closed --search ...`). Vale un
     numero y lo que le paso.
   - **¿Donde acopla?** Vale el sitio concreto del que cuelga.
   - **¿Cual es el fichero de orquestacion del repo?** El uno o dos sitios donde un conflicto deja de
     ser cosmetico -el caso de uso que dirige el flujo, el entrypoint que monta las dependencias-. No
     cambia el corte, pero **decide el paso 7**: son carriles de uno.

   **Vara: si no puedes citar una ruta o un numero, no es un hallazgo, es una impresion**, y no entra.
   Es la misma vara de falsabilidad que gobierna los criterios de aceptacion, aplicada aguas arriba.

   **Acota la busqueda.** El objetivo es un punado de lineas que una persona pueda confirmar de un
   vistazo, no un informe: para cuando dejes de encontrar cosas nuevas, y quedate con lo que de verdad
   cambia el corte.

   Los hallazgos no se preguntan uno a uno: **la persona los ve y los corrige en el paso 1c**, en el
   bloque de lo que entiendes del codigo, porque ella sabe cual de esos precedentes se revirtio por un
   motivo que sigue vigente. Lo confirmado se escribe en la seccion `## Lo que ya existe` del issue padre, y **se usa en el paso 2**:
   una pieza reutilizable suele quitar una slice entera, y un precedente revertido suele cambiar el
   orden. **La linea `- pieza:` que se escribe aqui es solo el puntero**: que hace hoy esa pieza lo
   entiende el paso 1c, y es esa lectura -no la confirmacion de este paso- la que completa la linea
   antes de cortar.

   **Si no hay nada, dilo con esa seccion vacia y su motivo**, no la omitas: ausencia declarada y
   ausencia silenciosa no son lo mismo, igual que en `SENAL:` y en los controles.

1c. **Cierra el diseno: publica lo entendido del codigo, los criterios propuestos y las decisiones, y
   espera confirmacion antes de cortar (`check-alignment`).** Cierra el paso 1, cuando el bloque de
   arquitectura esta contestado o cerrado con su motivo y ya no queda abierta ninguna pregunta que pase
   los filtros. El paso 1b confirma punteros -rutas, numeros de issue, sitios de acople-; lo que no confirma nadie es que se entendio **que hace** el codigo que el corte va a tocar,
   **que se va a considerar hecho**, ni **que se decidio**. Hoy el primer momento en que un malentendido
   del flujo, un criterio que no era ese o una decision tomada a medias se puede ver es leyendo las
   subissues ya creadas, o la pull request de la primera slice con el run ya pagado.

   Publica cuatro bloques y **espera confirmacion de los cuatro**:

   - **Lo que entiendes del codigo**, con forma exigible: por cada pieza que el corte va a tocar, su
     ruta y **que hace hoy**. **Una linea que solo dice que el fichero existe no cumple**: eso ya lo
     dio el paso 1b, y este paso completa esa linea con el comportamiento antes de que el paso 2 la
     escriba en el padre.
   - **Los criterios de aceptacion de la feature entera**, con la misma **vara de falsabilidad** que
     gobierna los criterios de cada slice -nombra el cambio de produccion que lo haria fallar-, y
     **declara que esa vara se aplico**.
   - **Las decisiones de la persona**, una linea por decision: lo que decidio en el paso 1 -dominio,
     arquitectura y contratos con sus firmas, mas lo que contesto a las preguntas que pasaron los
     filtros- y que el implementador no tiene que adivinar.
   - **Las decisiones del agente**, aparte y una linea cada una: lo que decidiste tu porque no paso los
     filtros, sin incluir el dominio, la arquitectura y los contratos, que son de la persona; lo que solo
     se cerro con su motivo no se lista. Estan aparte para que la persona las vete; una vetada vuelve como
     pregunta, y las que quedan se reparten igual que las de la persona.

   **Y que quepa de un vistazo**: una linea por pieza, una por criterio y una por decision,
   **no un informe**. Es la misma vara con la que el paso 1b acota su busqueda, y aqui pesa mas, porque lo que no
   se puede escanear se aprueba a ojo -y un gate que se aprueba a ojo no caza nada-. Si no cabe, la senal
   no es escribir mas pequeno: es que el corte abarca demasiado y hay que volver al diseno.

   Los criterios de feature **no se escriben en el issue padre**: seria un tercer sitio diciendo lo
   mismo que ya dicen las subissues, y derivaria en cuanto una slice cambie -el mismo motivo por el
   que **"el padre no repite las slices"**-. Viven en esta conversacion, y de aqui los reparte el paso
   siguiente. Las decisiones si tienen sitio propio, y el paso 2 las reparte.

2. **Trocea en slices verticales (guia activa), repartiendo lo confirmado en el paso 1c.** Carga
   `references/slicing.md` y aplica su procedimiento sobre el diseno aprobado: identifica el **walking
   skeleton** (slice #1), **saca delante el contrato de toda frontera** -un endpoint o un evento hacia
   fuera, pero tambien un puerto o un modelo compartido entre capas-, porque es lo que permite que sus
   dos lados se construyan a la vez en vez de en fila (paso 1b de `slicing.md`, y es de donde sale el
   paralelismo del paso 7), genera el resto por la **heuristica ordenada**, y decide tu el corte aunque no
   sea obvio: la persona lo ve y lo corrige en la lista corta del paso 2d. Valida cada slice contra los criterios de validez y el conjunto contra el
   **test de despriorizacion** e **igualdad de tamano**. Elige el `name` kebab-case de cada slice. Las
   lineas `ACEPTACION:` de cada slice salen de **repartir** los criterios de feature confirmados en el
   paso 1c, no de inventarlos aqui.

   **Reparte tambien las decisiones confirmadas en el paso 1c.** Una decision que afecta a una sola
   slice va a su linea `DECISION:`; una que afecta a varias se queda en `## Decisiones` del padre, una
   sola vez; y una slice que no recibe ninguna lleva `DECISION: ninguna - <motivo>`.

2a. **Escribe la intencion, la de la feature y la de cada slice.** El diseno del paso 1 ya
   entendio el problema: la seccion `## Intencion` es su destilado, no trabajo nuevo. Redactala con
   lo que esta mal hoy y como se nota, sin nombrar clases ni ficheros. Luego, slice a slice, escribe
   su `INTENCION:` y **pasale la vara**: nombra el cambio de mundo que la borraria; si no puedes
   nombrar nada roto o imposible, reescribela. Si al hacerlo descubres una slice cuya intencion no
   sabes nombrar, la senal no es "redactar mejor": es que la slice sobra o esta mal cortada, y eso se
   arregla volviendo al paso 2.

2b. **Disena la senal de cada slice (mientras el corte todavia se puede cambiar).** Carga
   `references/observabilidad.md` y, slice a slice, **baja la escalera**: ¿la senal ya existe gratis
   por la libreria del repo? ¿basta enriquecer lo que ya emite? ¿hace falta una metrica de negocio
   nueva (y entonces su emision es un criterio de aceptacion mas, con su test)? ¿o es un **gap de la
   libreria** que hay que declarar en vez de instrumentar a mano? Escribe la linea `SENAL:`
   resultante, o la exencion con su motivo. Decide tambien si el conjunto necesita **slice de
   alerta** y **slice de panel**: si las necesita, van con su `REPO:` y **detras** de la slice que
   emite la serie (orden forzoso); si no las necesita, que sea una decision explicita, no un olvido.
   Lo aplazable es la telemetria fina, no la senal minima.
2c. **Pregunta si la feature tiene una historia de usuario asociada (`check-alignment`).** No hay
   heuristica ni fichero que la derive: pregunta directamente por su clave (formato `HU-123` - una
   letra mayuscula, cero o mas letras mayusculas o digitos, un guion y uno o mas digitos) y **espera
   la respuesta**. Si la persona da una clave, comprueba que tiene esa forma -si no, dilo y vuelve a
   pedirla- y escribe la seccion `## Historia de usuario` del padre con ella; esa misma clave se
   antepone al titulo de cada subissue en el paso 5 y viaja a su etiqueta `origen:<clave>`. Si la
   persona dice que la feature no tiene historia asociada, no se escribe nada: sin esta pregunta el
   padre nunca tendria la seccion, porque ningun otro paso la deriva de lo que ya se ha discutido.
2d. **Propon el troceo en lista corta y espera confirmacion del troceo antes de seguir.** Va despues de
   2a y 2b porque esos pasos pueden quitar slices o anadir las de alerta y panel. Una linea por slice:
   `slice-NN (name)`, su intencion y de cual depende si depende de alguna. Es lo unico de las subissues
   que la persona revisa antes de crear, porque su cuerpo no esta escrito para leerse: puede cambiar
   nombres, orden o cortes, o pedir que se trocee de nuevo, y se le vuelve a ensenar hasta que lo
   confirme. El dialogo de la hamburguesa de `references/slicing.md` solo se abre si la persona rechaza
   la lista. Corregir un `name` aqui cuesta una linea; despues cuesta editar subissues, y de el sale la
   rama.
3. **Confirma las fuentes de convencion (`offload-deterministic` + `check-alignment`).** El paso 0 ya
   corrio el helper del repo del padre y el paso 1 los de cada repo destino; aqui se juzga lo que listaron
   y se escribe la seccion. El helper, para no asumir rutas ni inventarlas:
   `slice-runner discover-conventions <repo>`. Lista candidatos
   (docs y skills de proyecto) sin decidir. Juzga cuales son la vara de medir real, **proponselos a
   la persona y espera su confirmacion** (puede anadir o quitar). Si el helper no devuelve nada
   plausible o no se confirma ninguna, **para y pregunta** donde viven las convenciones: nunca emitas
   la spec con la seccion vacia. Con lo confirmado, redacta la seccion `## Fuentes de convencion`
   (punteros, no contenido: las convenciones siguen viviendo en el repo).

   **Una vez por repo destino.** Si alguna slice lleva `REPO:`, el mismo helper se corrio **sobre ese
   repo** (`slice-runner discover-conventions <ruta-del-repo-destino>`) en cuanto el diseno decidio que habia
   trabajo en el; confirmalo con la persona, y escribe sus
   punteros en la subseccion `### <org>/<repo>`. Cada repo tiene su propia vara: la del repo de
   manifiestos (templating, escaping, politica de labels de alerta) no se parece a la de la app, y
   heredar la equivocada es la desviacion silenciosa que esta seccion existe para evitar.
3b. **Confirma los controles del repo (mismo baile de tres pasos).** Si las fuentes son la
   vara, los controles son **los comandos con los que se mide**, y se declaran aqui por la misma razon:
   `slice-runner` no puede deducirlos en cada slice sin meter el `Makefile` en el contexto que tiene
   que durar todo el run, y dejarselo al implementador seria peor -el juzgado eligiendo su propia
   vara-. Corre el helper determinista:
   `slice-runner discover-controls <repo>`. Lista los targets del
   `Makefile` (con el comentario de encima como pista) y las herramientas configuradas en
   `pyproject.toml`/`tox.ini`, **sin decidir**. Propon el mapeo `nombre: comando` y **espera
   confirmacion**: es el paso que mas valor anade, porque ninguna autodeteccion sabe que este repo
   necesita levantar servicios antes, o que la suite entera es demasiado lenta para el bucle y hay un
   objetivo mas corto. Escribe la seccion `## Controles` con lo confirmado.

   - **Una vez por repo destino**, igual que las fuentes: cada `REPO:` lleva su subseccion
     `### <org>/<repo>`. Correr `make test` de la app contra el repo de manifiestos no valida nada.
   - **Un repo sin controles reales** (por ejemplo, uno cuya CI solo publica en `master` y no
     valida en PR) se declara con `- ninguno: <motivo>`. **No lo dejes vacio y no te inventes uno**:
     vacio hace que `slice-runner` pare, y un control inventado finge una garantia que no existe.
4. **Auto-validacion.** Aplica el checklist de `validate` (abajo) sobre lo que vas a crear -cuerpo del
   padre, titulo, etiqueta y cuerpo de cada subissue- y corrigelo antes de tocar GitHub. Lo que el
   checklist manda preguntar a la persona, en autoria pasa antes por los dos filtros de
   `references/diseno.md`.
4b. **Haz que otro lo refute (`feedback-flip`).** Pasale el borrador entero -padre y subissues, solo
   ese texto- a un subagente que no lo diseno, con el encargo de "La refutacion" de
   `references/diseno.md`: que se rompe, que lineas se contradicen, que criterio no se puede cumplir o
   medir, que afirmacion no se sostiene. Es el unico momento en que criterios, exclusiones y
   sustituciones existen a la vez, y es entre ellos donde se esconden las contradicciones. Sus
   objeciones pasan los mismos dos filtros del paso 1: las que los pasan, y cualquiera que contradiga
   una decision de la persona, van a ella con su recomendacion, y las que no las corriges tu y las nombras al cerrar (paso 6). Si alguna cambia el
   troceo, vuelve a ensenar la lista corta del paso 2d. Una sola pasada.
5. **Crea, sin volcar la spec por el terminal.** Crear es una accion visible en el repo de alguien y
   no se deshace facil, asi que **no crees nada sin el troceo confirmado en el paso 2d** ni con una
   objecion de la refutacion pendiente de la persona. Lo que no se hace es imprimir el cuerpo del padre
   y de cada subissue: la persona ya confirmo lo que tenia que confirmar, y el detalle lo lee en GitHub.
   Si el padre declara `## Diseno`, cada `### <nombre>` lleva solo la variante elegida: las descartadas
   se quedan en el artefacto y no viajan al padre.

   En este orden:

   - El padre: `gh issue create --repo <org>/<repo> --title "<feature>" --body-file -`, con el cuerpo
     del paso 2a/2c/3/3b. Si declaro `## Historia de usuario`, su titulo abre con la clave
     (`HU-123 <feature>`) y la llamada anade `--label origen:HU-123`. Si la variable de entorno
     `SLICE_RUNNER_WORKSPACE` esta definida, la ultima linea del cuerpo, despues de `## Controles`, es la
     marca con ese uuid, en la forma de `contract/workspace-marker.json`; si no lo esta, no se escribe nada.
   - Cada slice, en orden de `slice-NN`, como hija suya:
     `gh issue create --repo <org>/<repo> --title "slice-NN (name): <titulo>" --body-file - --parent <N> --label estado:pendiente`,
     donde `<N>` es el numero del padre. El `--parent` es lo que la hace slice de esa feature y la
     `--label` es su estado macro inicial.
   - Si `gh` responde que la etiqueta no existe en el repo, creala una vez
     (`gh label create estado:pendiente --repo <org>/<repo>`) y reintenta: una subissue sin etiqueta de
     estado es una slice sin estado que nadie puede consultar.
   - Si el padre declaro `## Historia de usuario`, el titulo lleva la clave delante
     (`HU-123 slice-NN (name): <titulo>`) y el comando anade `--label origen:HU-123` a la misma
     llamada, junto a `--label estado:pendiente`. Si `gh` responde que esa etiqueta tampoco existe, se
     crea igual que la de estado (`gh label create origen:HU-123 --repo <org>/<repo>`) y se
     reintenta.
   - Despues de crear la ultima subissue, `slice-runner register <N> --repo <org>/<repo>`: deja en el
     registro local una fila `pending` por cada subissue abierta, para que el panel de la interfaz
     muestre la feature antes del primer run. Si falla no se deshace nada ni se repite la creacion: el
     panel solo queda vacio hasta el primer run.
6. **Cierra** diciendo el numero/URL del padre, las subissues creadas con su numero, lo que la
   refutacion corrigio sin preguntar -una linea cada cosa-, y que se ejecuta con
   `slice-runner run <N> --repo <org>/<repo> --base master`, una invocacion por slice.

   **El comando no lleva ruta de worktree y este es el unico sitio que explica por que.** El programa
   monta el suyo, colgando de la raiz del clon, y el run se lanza desde esa raiz. Antes la ruta se
   tecleaba y su valor por omision era el directorio actual: medido en dos maquinas, era el mecanismo
   por el que el juez leyo **31 de 32 veces** una rama que no tenia nada que ver con la slice que
   juzgaba. Que hace el programa segun lo que encuentre montado, y que significa `bloqueada:worktree`,
   esta en **"El worktree de una slice"**.

7. **Propon el reparto en paralelo y, si te lo confirman, montalo tu.** Una invocacion conduce **una**
   slice, asi que una feature de ocho son ocho invocaciones; en serie eso es toda la tarde. Se pueden
   correr a la vez en **worktrees distintos**, y quien acaba de trocear es quien mejor sabe que va a
   tocar cada slice, asi que la propuesta se hace aqui y no se deja para que la improvise otro.

   **El reparto lo decides por semantica: no hay helper, y el riesgo se declara en vez de negarse.**
   Lee lo que acabas de trocear y estima, slice a slice, **que ficheros va a tocar**. Luego cruza las
   estimaciones. Lo que **no** vale es la conclusion comoda: decir "son disjuntas" es lo que ha fallado
   dos veces en este flujo -una pareja elegida como la mas disjunta mirando su fichero protagonista
   compartio cuatro ficheros, y otra compartio siete, incluido uno que **las dos crearon**-. La forma
   honesta es *"comparten `<fichero>`; si hay conflicto sera pequeno"*, y **no** *"no se tocan"*.

   Tres reglas duras, que no dependen de lo bien que estimes:

   - **Dos slices que toquen el mismo fichero de orquestacion no van juntas.** En todo repo hay uno o
     dos ficheros donde el conflicto deja de ser cosmetico y pasa a ser logica que hay que rehacer.
     Identificalos en el paso 1b y trata cada uno como un carril de uno.
   - **Los ficheros iman se comparten casi siempre**: el entrypoint que monta las dependencias, los
     dobles de test, el vocabulario de errores, el `README.md` y los docs de convencion. Compartir uno
     no impide lanzar; **garantiza una fusion**, y la segunda en mergear la resuelve.
   - **Una slice que depende de otra va detras**, nunca al lado. Si el paso 1b encontro un `- acopla:`
     entre dos, esas dos son secuenciales aunque toquen ficheros distintos.

   Presenta el reparto en **tandas**, y para cada slice di su worktree y el solape que esperas.
   **Espera confirmacion** (`check-alignment`): crear worktrees y lanzar runs gasta dinero en el
   harness de otra persona.

   Con la confirmacion dada, lanza cada run: el programa monta un worktree por slice, como cuenta
   **"El worktree de una slice"**, asi que dos runs en paralelo solo necesitan slices distintas.

   ```bash
   slice-runner run <padre> --repo <org>/<repo> --base <base> --slice <identificador>
   ```

   Cada run **en background**, nunca encadenados en una shell que bloquee: son procesos largos y el
   principio de este flujo es que ninguna espera congele una sesion.

   **Y con la salida a la vista: no la redirijas a un fichero ni la pases por una tuberia.** Quien lanza
   el run no es quien lo mira. Desviada, la persona se queda sin ver que esta pasando en un proceso que
   dura tres cuartos de hora y cuesta decenas de dolares, y la unica forma que le queda de enterarse es
   pedirtelo a ti, turno a turno. Una tuberia ademas puede dejarla en nada: el proceso escribe a bloques
   cuando el otro extremo no es un terminal, asi que matar el run se lleva lo que aun no habia salido.
   Si solo te interesa el final, **recorta al leer, no al escribir**.

   Y avisa de lo que viene despues: **cada run para en la comprobacion previa si a su slice le faltan
   decisiones**, asi que N runs en paralelo son N comprobaciones que pueden cortar, no una.

## Steps — modo `validate`

Revisa una spec existente -el padre `#N` y sus subissues- contra el contrato y reporta cada desviacion con
**la regla que incumple y su ubicacion**: `issue padre` cuando esta en el cuerpo del padre, y
`slice-NN (#numero)` cuando esta en una subissue, diciendo si esta en el titulo, en la etiqueta o en el
cuerpo. Sin ubicacion la persona tiene que buscarla, y en una feature de doce slices eso es medio
trabajo. Ofrece corregirlas. Checklist:

- **Hay un issue padre y una subissue por slice, y cada subissue es hija de el.** Si alguna esta
  suelta, es desviacion: `slice-runner` no la vera, porque busca por `parent-issue:<org>/<repo>#<N>`.
  Un padre con checklist de slices en el cuerpo es del formato viejo, y eso se termina con la version
  vieja de estas skills, no se convierte a medias.
- Cada subissue tiene titulo `slice-NN (name): titulo` -con la clave de la historia de usuario
  delante si el padre la declaro-, con `NN` de dos digitos sin huecos ni repetidos y `name` en
  kebab-case unico dentro de la feature, y al menos una linea `ACEPTACION:` en su cuerpo.
- **El parentesis no lleva nada mas que el `name`.** Un type de conventional commit delante, del
  estilo `(refactor: extraer-repo)`, es desviacion: el programa se lleva el parentesis entero como
  nombre y deriva una rama que git rechaza.
- **El padre declara `## Historia de usuario` pero su propio titulo no abre con la clave, o no lleva
  la etiqueta `origen:<clave>`.** Las dos mitades sirven para lo mismo -encontrar la feature entera
  sin abrirla- y las dos se corrigen igual: reportalo como `issue padre`, diciendo cual de las dos
  falta.
- **El padre declara `## Historia de usuario` pero alguna subissue no lleva la clave en el
  titulo.** Si el padre trae la seccion y el titulo de una subissue no empieza por esa clave seguida
  de `slice-NN`, es la desviacion a corregir: reportala como `slice-NN (#numero)`, en el titulo,
  citando la regla de que la clave va delante del `slice-NN`.
- **Cada subissue tiene su etiqueta de estado macro**, y es una del vocabulario (`estado:pendiente` al
  crearla; luego las que escribe slice-runner). Un estado escrito en el texto en vez de como etiqueta es
  desviacion: nada lo lee, y desmiente a la etiqueta en cuanto las dos existen. Un cuerpo que traiga a
  mano el bloque `<!-- slice-runner:estado ... -->` es la misma desviacion al reves: ese bloque es de la
  maquina.
- **Tiene seccion `## Lo que ya existe`**, y cada linea cita una ruta o un `#numero`. Si falta (p. ej.
  un issue anterior a este mecanismo), **es la desviacion a corregir**: corre el descubrimiento
  (paso 1b), confirmalo con la persona y anadela. Una linea sin referencia comprobable -"el repo ya
  tiene puertos"- se reescribe o se quita: lo que no se puede ir a mirar no informa el corte. **Una
  linea `- pieza:` no dice que hace hoy esa pieza**: nombrar una ruta que existe deja de cumplir la
  vara, y se reescribe con el comportamiento, reportandola como `issue padre`. Ausencia real se
  declara con `- nada: <motivo>`, nunca dejando la seccion vacia.
- **Tiene seccion `## Intencion` con texto**, y **ninguna slice sin linea `INTENCION:`**. Si falta
  (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**: reconstruyela con la
  persona y anadela. Comprueba tambien la **vara** en cada linea: nombra el coste de no hacerla. Si
  dice "mejorar", "limpiar" o "refactorizar" sin decir que esta mal hoy, reescribela. Y si la linea
  describe el codigo (que clase se introduce, que fichero se toca) en vez del problema, tambien: eso
  es lo que el diff ya cuenta, y ocupa el sitio de lo que no cuenta.
- Ninguna slice sin criterios de aceptacion en su cuerpo (sin ellos no hay control de verificacion en
  slice-runner).
- **Ninguna slice sin al menos una linea `DECISION:`, y ninguna `DECISION: ninguna` sin motivo
  escrito.** Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  pregunta a la persona que decidio de diseno al cortar esta slice y anade las lineas, reportandola
  como `slice-NN (#numero)`, en el cuerpo; sin ellas `slice-runner` para con `missing-decisions`.
- **Cada `DISENO:` nombra un diseno que existe.** Si una subissue lleva `DISENO: <nombre>` y el padre no
  tiene `### <nombre>` dentro de `## Diseno` -o no tiene la seccion-, **es la desviacion a corregir**:
  `slice-runner` para con `unknown-design`. Reportala como `slice-NN (#numero)`, en el cuerpo, citando
  el nombre. Y un `### <nombre>` de `## Diseno` sin bloque de codigo no tiene HTML que viaje: reportalo
  como `issue padre`. La ausencia de `DISENO:` en una slice no es desviacion: es opcional.
- **El padre tiene seccion `## Decisiones` con al menos una linea.** Si falta (p. ej. un issue anterior
  a este mecanismo), **es la desviacion a corregir**: pregunta a la persona que decidio de diseno al
  disenar la feature y anadela al cuerpo del padre; una feature sin decisiones se declara con
  `- ninguna: <motivo>`, nunca vacia.
- **Ninguna slice que cambie comportamiento en prod sin `SENAL:`**, y ninguna `SENAL: exenta` sin
  motivo escrito. Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  aplica la escalera de `references/observabilidad.md` con la persona y anade la linea. La `SENAL` debe
  ser **refutable**: nombra la serie, la ventana y el assert; si dice "se monitoriza" o "no empeora",
  reescribela.
- **Ninguna slice sin `EXCLUYE:`, y ninguna `EXCLUYE: nada` sin motivo escrito.** Si falta (p. ej. un
  issue anterior a este mecanismo), **es la desviacion a corregir**: pregunta a la persona que decidio
  dejar fuera al cortar esta slice -si de verdad nada, la exencion lleva motivo- y anade la linea,
  reportandola como `slice-NN (#numero)`, en el cuerpo.
- **Ninguna slice sin `SUSTITUYE:`, y ninguna `SUSTITUYE: si` sin las dos mitades.** Si falta (p. ej. un
  issue anterior a este mecanismo), **es la desviacion a corregir**: pregunta a la persona si el diff de
  esta slice sustituye algo que ya esta funcionando y anade la linea, reportandola como
  `slice-NN (#numero)`, en el cuerpo. Un `si` que nombra solo una de las dos cosas que debe es la misma
  desviacion: sin el mecanismo de vuelta atras el verificador no tiene contra que exigirlo en el diff.
- **Y la segunda mitad tiene que ser la que corresponde al sujeto**, no solo estar. Un programa que se
  instala con una vuelta atras "sin redeploy" es la desviacion mas comun de esta linea: ahi volver atras
  **es** reinstalar, asi que esa mitad no informa de nada y hay que reescribirla por la que si muerde
  -que deja ilegible de lo que ya esta escrito, y que pasa con lo que ya existe-. Se caza leyendo la
  linea contra el repo destino, no contra su forma.
- **Cadena de observabilidad**: si alguna slice emite una senal nueva relevante, comprueba que hay slice
  de alerta (y de panel si aporta) **con su `REPO:`** y **detras** de la que emite la serie, o que la
  ausencia es una decision explicita. Nunca alerta/panel en la misma slice que la metrica.
- **Toda slice con `REPO:` tiene su subseccion `### <org>/<repo>`** en las fuentes de convencion **y
  en los controles**. Si falta cualquiera de las dos, es desviacion: corre el descubrimiento
  correspondiente sobre ese repo y anadela.
- **El padre tiene seccion `## Controles` con al menos una linea** para su propio repo. Si falta (p. ej.
  un issue de cuando `slice-runner` los autodetectaba), **es la desviacion a corregir**: corre
  `slice-runner discover-controls`, confirma el mapeo con la persona y anadela; sin ella `slice-runner` para.
  Un repo que de verdad no tiene controles se declara con `- ninguno: <motivo>`, nunca vacio, y esa
  linea no lleva controles al lado ni se lee como un comando.
- **Los comandos declarados siguen resolviendo.** Este es el sitio donde se caza la deriva: si alguien
  renombro un target del `Makefile` despues de crear el padre, corrigelo aqui. En tiempo de run no hay
  red -el control falla como cualquier otro y la slice acaba con `bloqueada:controles`-, y esa fue una
  decision consciente para no anadir un pre-flight heuristico.
- **Ninguna linea de la slice contradice a otra de la misma slice.** Es el unico item que no se ve
  leyendo una linea sola, y el mas caro cuando se escapa: se descubre con el diff delante y tres rondas
  de juez despues. Dos cruces, siempre: **que lo que `SUSTITUYE` promete no lo prohiba `EXCLUYE`** -paso
  de verdad: una slice pedia separacion fisica entre generaciones y su propio `EXCLUYE` prohibia
  renombrar los ficheros, que era lo unico que la lograba, y el implementador tuvo que elegir cual
  incumplir- y **que lo que un criterio exige no lo excluya otra linea**. Con contradiccion, la
  desviacion se corrige decidiendo cual de las dos lineas se queda, no dejandosela a quien implemente.
- **Ningun criterio se mide con algo que el verificador no recibe.** Recibe el diff, la spec y las
  fuentes de convencion; **no** recibe el informe del implementador. Un criterio que diga "el informe
  nombra..." es desviacion aunque sea falsable y aunque el implementador pueda cumplirlo: reescribelo
  apuntando al diff. Se reconoce con una pregunta: *¿con que lo comprueba quien tiene que medirlo?*
- **Cada criterio es falsable** (no basta con que exista). Por cada uno, nombra el cambio de
  produccion que lo haria fallar; si no puedes nombrarlo, **es la desviacion a corregir**:
  reescribelo con la persona hasta que sea refutable (o pregunta que se pretendia). Un criterio vago
  pasa el check de existencia pero deja sin dientes el mapeo criterio↔test del verificador de
  slice-runner.
- **Un criterio que pide una cantidad dice cuantas.** Si el comportamiento que pide solo se distingue
  de lo que ya hacia el programa con **mas de una ocurrencia** -"cada vuelta deja su commit", "por cada
  X hay un Y"- y el criterio no dice cuantas hay que ver, **es la desviacion a corregir**: el
  implementador lo pinea con una y quien juzga exige varias, los dos cumpliendo lo escrito, y el
  desacuerdo no se ve hasta que el presupuesto esta gastado. Se reconoce con una pregunta: *¿el caso de uno se distingue de lo que el programa ya hacia?* Si con una
  sola ocurrencia el criterio lo cumpliria tambien el codigo de antes, el numero va escrito.
- **Y cada criterio cae dentro de lo que el implementador puede hacer.** Si pide un commit, un mensaje
  de commit, una rama o texto del cuerpo de la pull request, **es la desviacion a corregir**: no lo
  puede cumplir nadie, y se descubre tarde, cuando la vuelta ya esta pagada. Reescribelo apuntando a lo
  que si esta en su mano -normalmente, que lo declare en su informe-. Esta es la unica desviacion del
  checklist que **no se ve leyendo el criterio solo**: hay que preguntarse quien lo cumpliria.
- **Si la slice traslada logica, sus criterios piden la retirada, no solo la red.** Un criterio que
  solo diga "los tests de donde estaba siguen verdes sin tocarlos" **es la desviacion a corregir**:
  describe el estado de mitad del trabajo, y cumplirlo al pie de la letra deja la cobertura duplicada
  para siempre. Anade el criterio que dice que sale de donde estaba, y el que protege las mitades: lo
  que ademas fijaba una transicion, una etiqueta o algo que cruza invocaciones se queda.
- **El padre tiene una seccion `## Fuentes de convencion`** con al menos un puntero (`- doc:` /
  `- skill:`). Si falta (p. ej. un issue anterior a este mecanismo), **es la desviacion a corregir**:
  corre el descubrimiento (paso 3), confirmala con la persona y anadela al cuerpo del padre. Este modo
  es el unico sitio que rellena un padre sin la seccion: slice-runner solo la consume, no la genera.
- **Y cada fuente es un fichero que existe y se puede leer**, no un directorio ni una ruta que se
  movio. **Compruebalo de verdad, una por una, contra el repo**: es el unico item de este checklist que
  no se decide leyendo el issue. Un directorio como `docs/conventions/` valia cuando las fuentes eran
  punteros que el implementador abria y elegia; desde que **su contenido viaja dentro del prompt**, una
  fuente que no se puede leer para el run en los prechecks, antes de escribir nada. Si encuentras una,
  la desviacion se corrige **listando los ficheros** que de verdad son la vara del codigo -no todos los
  que haya en la carpeta: `git-workflow.md` y el `CLAUDE.md` los lee una persona en sesion, no quien
  implementa-. Es la revision que hay que pasarle a **todo issue creado antes de que la vara viajara en
  el prompt**, y hacerlo aqui cuesta un minuto; descubrirlo al lanzar cuesta el lanzamiento.
- Nombres unicos y estables (no colisionan al derivar ramas `slice/NN-name`).
- **Calidad del corte** (contra `references/slicing.md`): cada slice es vertical, desplegable sola y
  reversible; el conjunto pasa el **test de despriorizacion** (hay >=1 slice que se podria posponer)
  y tiene **tamano equilibrado**; ninguna slice nombrada por capa tecnica salvo horizontal
  justificado; cuando una slice sustituye comportamiento en prod, nombra su mecanismo seguro (flag /
  expand-contract).

Si todo cumple: reporta `spec valida` y recuerda que se ejecuta con
`uv run slice-runner run <N> --repo <org>/<repo> --base master`.

## Fin

Reporta: numero/URL del issue padre, las subissues con su numero y su nombre, y el comando para
ejecutarla (`uv run slice-runner run <N> --repo <org>/<repo> --base master`, una invocacion por slice). No implementes nada: ese es el trabajo de
`slice-runner`.
