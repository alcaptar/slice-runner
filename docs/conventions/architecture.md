# Arquitectura y herramientas

## Los dos tipos de código Python de este repo

No es lo mismo y no se miden igual:

| | `src/slice_runner/` | `skills/*/scripts/*.py` |
|---|---|---|
| Que es | El programa orquestador | Los scripts deterministas que invoca una skill |
| Quien lo lanza | `uv run slice-runner` (el ejecutable que declara `[project.scripts]`) | La skill, con el `python3` de la maquina |
| Dependencias | `pydantic`, y **nada de `skills/`** | **stdlib puro**, sin excepción |
| Convenciones | Las cumple entero | Deuda declarada (ver `CLAUDE.md`) |

Los scripts son stdlib puro **porque no hay `uv` que resuelva nada** cuando los lanza la skill: una
dependencia ahi es un fallo en la maquina de otra persona.

## Estructura del programa

```
src/{paquete}/
  domain/
    {value_object}.py     un value object por modulo
    {enum}.py             un vocabulario cerrado por modulo
    {puerto}.py           un puerto por fichero
    {politica}.py         logica pura con su configuracion inyectada
    exceptions.py         las excepciones del dominio
  application/
    actions/{name}.py     casos de uso que mutan estado
    queries/{name}.py     casos de uso de solo lectura, con un puerto detras
  infrastructure/
    {impl}_{puerto}.py    el adaptador se llama como su implementacion
    {payload}.py          un modelo de frontera por concepto
    {agente}_{rol}.py     lo que define un agente invocado: su rubrica, sus herramientas, lo que lee
    cli.py                entrypoint
  tests/                  co-localizados, espejando las capas de arriba
    mothers/              Object Mothers
    payloads/             sobres reales grabados (su regla, en docs/conventions/testing.md)
  py.typed
  __main__.py
```

- **Un concepto por módulo, y con el lo que no existe sin el.** La regla no cuenta clases -contarlas es
  un censo con otra cara, y obliga a partir en dos ficheros lo que solo se lee junto-: pregunta por la
  dependencia. **La vara es dura a propósito: si borras el concepto principal, ¿el otro tipo se queda sin
  ningún consumidor y sin sentido propio?** Solo entonces comparten fichero. El caso claro es el
  vocabulario cerrado que solo clasifica un campo de ese value object, o la carga que un puerto recibe y
  que nadie más construye.

  **Y al reves: un tipo con vida propia es un concepto y va a su módulo**, aunque hoy se use al lado del
  otro. Tiene vida propia si lo construye otro sitio, si lo consume otra capa o si lleva su propia
  algebra. Sin esa mitad, "no existe sin el" se estira hasta justificar cualquier agrupación por
  costumbre.

  Las excepciones del dominio son la excepción a la regla y viven juntas en `domain/exceptions.py`, porque
  se leen como un catalogo y quien las captura suele querer ver la jerarquía de una vez.
- **Un puerto que solo consume la infraestructura vive con su adaptador**, no en `domain/`, junto a la
  excepción que lanza. El caso típico es el que lanza subprocesos: el dominio no los lanza ni sabe que
  existen, y subirlo metería ahí ese vocabulario, que es exactamente lo que esa capa se define por no
  tener. Consecuencia: `domain/exceptions.py` es el catalogo de las excepciones **del dominio**, no de
  todas las del programa.

  **Y la premisa se comprueba cada vez, porque caduca**: en cuanto un caso de uso necesita ese puerto,
  vuelve a `domain/`, que es donde vive por defecto todo lo que el dominio necesita.
- **Los tests del programa viven dentro del paquete**, no en `tests/`, y espejan la estructura de las
  capas **que se testean**. No hay un árbol de tests de dominio, y no es un olvido -la estrategia es
  outside-in y lo de dentro del dominio se cubre por ese camino-. El reparto de los dos árboles y el
  porque están en `docs/conventions/testing.md`.
- El flujo de dependencias va hacía dentro: `infrastructure` conoce `application` y `domain`,
  `application` conoce `domain`, y `domain` no conoce a nadie.

## Una regla de negocio se escribe una vez

La regla de tres gobierna el **parecido del código**: trozos que se repiten se extraen cuando extraerlos
deja el sitio mejor, y hasta entonces esperar es correcto. **No gobierna donde vive una decisión.** Una
regla de negocio -que desbloquea que, cuando se agota algo, que cuenta como que- se escribe **una vez**, y
la primera copia ya es el fallo: no hay umbral que la autorice, porque lo que se rompe no es la limpieza,
es la coherencia.

La diferencia no es de grado. Dos trozos de código parecidos que divergen dejan código feo; **dos sitios
que deciden lo mismo y divergen dejan un programa que se contradice**, y el síntoma no aparece donde esta
la copia sino donde alguien la creyo.

**La vara: si esta decisión cambiara, ¿cuántos ficheros hay que tocar para que el programa siga siendo
coherente?** Uno, o está repartida. La pregunta se hace sobre el cambio, no sobre el texto: **dos sitios
que hoy dicen lo mismo con palabras distintas ya están repartidos**, y por eso la vara no puede ser el
parecido -un detector de duplicado no los empareja-.

### Que no cuenta

**El idioma de una frontera no es una regla.** Comprobar el código de salida en cada adaptador que lanza
un proceso, o la forma del sobre en cada modelo que valida uno: eso es la misma frase, no la misma
decisión, y cada sitio contesta por lo suyo. A eso si le aplica la regla de tres, y no urge.

La pregunta que los separa: **¿existe un cambio de negocio que obligue a tocar los dos a la vez?** Si no
lo hay, es idioma.

### Donde vive cuando se extrae

Donde ya dice `docs/conventions/domain.md`: la regla exacta es un objeto del dominio, y quien la necesita
**pregunta**.

```python
# ejemplo/domain/{politica}.py
class {Politica}:
    @staticmethod
    def of_the_{caso}({caso}: {Caso}) -> {Desenlace}: ...


# ejemplo/application/actions/{conducir}.py -- pregunta, no reimplementa
desenlace = {Politica}.of_the_{caso}({caso})
if desenlace is not {Desenlace}.{LIMPIO}:
    return self._{cerrando}(desenlace)
```

Lo que se repite en el consumidor -comparar el desenlace contra el vocabulario- es consumir la respuesta,
no reimplementarla. Lo que **no** vale es extraer a un helper que las dos copias llamen desde donde
estaban: eso deja la decisión repartida con una indirección delante.

**Y un value object que tiene el dato posee la pregunta.** Si cada consumidor deriva a mano la condición a
partir de un campo del objeto, la regla está repartida entre ellos aunque el campo viva en un solo sitio:
el campo no es la decisión.

### Cuando la copia es inevitable

Hay reglas que cruzan una frontera de proceso y **tienen** que existir dos veces: las dos mitades de un
contrato, un dato del código que además se escribe en prosa. Ahi la copia se **declara y se mide con un
contrato que compare las dos**, con la forma y el límite que fija `docs/conventions/como-se-escribe.md`.
Lo que no vale es dejarla implícita: una copia que nadie compara va a divergir, y la única diferencia con
el caso de arriba es que esta se sabia.

### La red que hay, y su agujero

Un `match` exhaustivo sin rama genérica hace que añadir un miembro a un vocabulario rompa en `mypy`, y por
eso se exige. **Pero obliga a mencionar el miembro nuevo, no a clasificarlo igual en todos los sitios**:
una partición de un vocabulario declarada en varios sitios compila con el miembro nuevo puesto en la
familia equivocada en uno de ellos. La exhaustividad protege del olvido, no del reparto, y la partición
que se repite se declara una vez como cualquier otra regla.

### Por que esta regla vive aquí y no en un linter

Porque este programa lo escribe un arnés que **no puede aprender**: cada invocación empieza sin memoria de
las anteriores, así que cuando necesita una regla que ya existe en otro fichero no la reutiliza -no sabe
que esta-, la vuelve a derivar donde le hace falta. Lo que produce eso no son copias literales, son
redacciones distintas de la misma decisión, y no hay herramienta que las empareje por su forma. **El único
sitio donde se puede cazar es cuando alguien escribe la segunda**, con la pregunta del cambio delante.

## Herramientas

Python 3.11+, `dataclasses` frozen para value objects, `abc` para puertos, `StrEnum`/`IntEnum` para
vocabulario cerrado, `unittest.mock` para dobles, `pytest`, `mypy` strict, `ruff`, `uv` para el
toolchain, `argparse` para la interfaz de línea de comandos.

**`pydantic` solo en la frontera externa.** Los value objects y los DTOs internos son dataclasses
frozen; Pydantic aparece unicamente en los modelos que cruzan la frontera del proceso. El razonamiento
está en `docs/conventions/infrastructure.md`.

### Desviación declarada respecto a la vara secundaria

La skill de buenas practicas de backend que se usa como vara secundaria dice **"dataclasses frozen, sin pydantic"** para dtos,
params, value objects y events. Aquí se cumple en todo eso, y se diverge en un solo sitio: **el esquema de la frontera
externa**.

El motivo es que esa vara asume Django + Django REST Framework, donde los serializers ya validan
la entrada y generan el esquema OpenAPI. Aquí no hay capa de serializers: la frontera es el JSON de un
subproceso, y el esquema **hay que generarlo** para mandarselo al juez. Sin Pydantic eso son tres
copias del mismo contrato cosidas a mano, que es de donde se viene.

Lo que **no** autoriza esta desviación: Pydantic en `domain/`, ni en los `Params` de un caso de uso,
ni como sustituto de un value object.

## Decisiones de configuración que no se re-litigan

Razonadas en `pyproject.toml`:

- **`ruff` no formatea los `.md`**: aquí los `.md` son el producto (las skills y sus reference-docs),
  y sus ejemplos se escriben para leerse.
- **Las reglas `S` (bandit) están desactivadas**: sus hallazgos son inherentes al cometido de los
  scripts de `skills/` que lanzan procesos externos, y obligarian a sembrarlos de `noqa` sin cambiar
  una sola decisión.

## Antipatrones

- Una dependencia de terceros en `skills/*/scripts/`. **La lanza la skill sin `uv`: hay que resolverlo
  con stdlib.**
- Pydantic en `domain/` o en los `Params` de un caso de uso.
- `domain/` importando de `application/` o de `infrastructure/`.
- Una regla de negocio escrita en dos sitios, **aunque las dos redacciones sean distintas**.
- La misma partición de un vocabulario cerrado declarada en más de un sitio. **El `match` exhaustivo no
  protege de esto.**
- Un helper que las dos copias llaman desde donde estaban. **La decisión sigue repartida, ahora con una
  indirección delante.**
- Un value object que tiene el dato y no la pregunta, con cada consumidor formulandola a mano.
- Una copia inevitable de las dos mitades de un contrato **sin un test que las compare**.
