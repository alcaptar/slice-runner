# Capa de infraestructura

Adaptadores de los puertos, modelos de frontera y entrypoints. Es la única capa que sabe que hay un
subproceso, un `git` o un sistema de ficheros al otro lado.

## Lo que llega de fuera se valida al entrar

Sin excepción, y sin `cast`: un `cast` no comprueba, solo calla a `mypy`.

- **En la frontera del programa, el esquema es Pydantic**, un `BaseModel` por concepto, sobre una base
  comun que fija `extra="forbid"`, la traducción del `ValidationError` y el volcado al contrato.
- **En los scripts de `skills/`, dataclass con `from_dict`/`from_row` a mano**, que rechaza clave
  desconocida y tipo equivocado. Son stdlib puro (ver `docs/conventions/architecture.md`), así que no
  hay Pydantic que usar.

## Modelos de frontera

- `extra="forbid"`: una clave que no conocemos es un **rechazo**, no un campo ignorado. Significa que
  el otro lado cambio de forma y nuestras suposiciones pueden estar viejas.
- `frozen=True` y `populate_by_name=False`: se entra por el `alias`, que es el nombre del contrato, y
  no por el nombre del campo.
- **Un `alias` por campo, y de ahi sale todo lo que ve el otro lado**: el esquema que se le manda, la
  validación de lo que devuelve y el JSON que emite la interfaz de línea de comandos. Un contrato que
  se escribe más de una vez necesita un test solo para que sus copias no divergan.
- La conversión al dominio vive en el modelo: `from_domain(cls, entity) -> Self` para entrar,
  `to_domain(self)` para salir. **Nunca un helper de mapeo en el caso de uso.**
- Un `ValidationError` de Pydantic no sale de la capa: se traduce a la excepción del dominio que el
  entrypoint sabe mapear.

### Un formato ajeno de vocabulario abierto se valida por proyección

Cuando lo que llega **no es un contrato que este programa defina ni del que dependa una versión fija**
-la transcripción de una sesión del harness, el JSON de una herramienta externa-, exigir
`extra="forbid"` sobre el objeto entero rompe la lectura con cada campo que el otro lado añada, que es
justo la función que ese lector tiene. La regla se mantiene invirtiendo el orden: se **proyecta a mano**
un diccionario con exactamente las claves que se consumen y se valida esa proyección, que sigue siendo
`extra="forbid"`. Una clave que si declaramos conocer y que falta o llega con el tipo equivocado sigue
rompiendo.

Distinguir los dos casos es lo que hace legitima la excepción: un fichero que **este programa escribe
entero**, o una salida documentada de la que dependemos, se valida completo. Y una línea que no es JSON
es corrupción, no una variante más de un vocabulario abierto: se lanza en vez de tragarse.

### `strict=True` por campo, no a nivel de modelo

A nivel de modelo rompe el parseo: en modo estricto un `StrEnum` deja de aceptar su propia cadena y un
modelo anidado deja de aceptar un `dict`.

Por campo, donde la coerción es peligrosa: un booleano que dice si algo fallo -sin estricto, la cadena
`"no"` se convierte en `False`, o sea el otro lado declarando el fallo y el programa leyendo que no
hubo- y un número que puede llegar como texto.

La vara para decidir: **¿que valor equivocado pasaría por bueno, y que decisión tomariamos con el?**
Si la respuesta es "ninguna que importe", laxo vale.

### El esquema se emite plano

`JsonSchema.flat` resuelve los `$ref` y borra los `title`. Dos motivos: la **forma plana es la única
medida de verdad** contra un `claude -p` real, y los `title` solo gastan tokens del prompt. Hay un test
que falla si vuelve a colarse una referencia.

### Un esquema que viaja en un prompt declara **un solo campo**

El harness pierde la frontera entre parametros cuando el modelo emite la llamada a `StructuredOutput`:
el primero se traga su propio cierre y todo lo que venga detrás, así que el segundo llega como texto
dentro del primero y el validador lo reporta como **campo requerido que falta**. La medición que lo
fijo está en la pull request que lo introdujo.

Y el daño no acaba en el rechazo. Tras dos o tres, el modelo minimiza para aislar el fallo, el informe
mínimo si valida, y **se pública relleno con la firma del programa**. Por eso la regla es la forma del
esquema y no una instrucción más en el prompt: un brief que pida el campo que falta no puede arreglar
una frontera que se pierde en el transporte.

Consecuencia: el modelo declara un único campo y el adaptador **pública lo que llega en vez de
componerlo**. Se pierde que el programa garantice las secciones; se gana que no haya forma de fallar la
forma.

**El `description` no es un `title` y por eso se queda.** Un `title` repite el nombre del campo, así que
solo gasta; un `description` dice **que se pone ahi**, y es lo único que el agente tiene delante en el
momento de emitir -el brief queda cientos de líneas más arriba, y `--json-schema` no restringe la
generación, solo valida después-. **Consecuencia: donde el esquema describe un campo, el prompt no lo
vuelve a describir**, y hay test que lo mide. Solo lo llevan los payloads cuyo esquema viaja en un
prompt; los que declaran esquema para un almacen durable no lo necesitan, porque ahi nadie emite contra
el esquema.

### El `alias` traduce; cuando no hay nada que traducir, no se escribe

Un contrato que fijamos nosotros y está en ingles ya tiene la clave en el nombre del campo, y un `alias`
idéntico solo sería ruido que hay que mantener en dos sitios. `by_alias=True` cae en el nombre del campo
cuando no hay alias, con lo que el esquema, la validación y la salida siguen saliendo de un solo sitio,
que es lo que la regla protege.

### Un campo que se llama como un builtin rompe las anotaciones de la clase

Pydantic evalua las anotaciones **con el namespace de la clase**, así que en un modelo con un campo
llamado como un builtin -`type`, porque el otro lado trae esa clave- una anotación que use ese builtin
explota al importar el módulo. Por eso lo que necesite el builtin **entra como argumento** y no como
`ClassVar` de la clase. Ni el `strict` ni el `from __future__ import annotations` cambian nada aquí.

### Cuidado con `TC002` y las anotaciones de Pydantic

Pydantic resuelve las anotaciones de campo **en runtime** al crear el modelo. Un tipo que `ruff` mueva
a `if TYPE_CHECKING:` deja el modelo *not fully defined* y **revienta en la primera validación, no al
importar**: un smoke que solo importe el módulo lo da por bueno. Lo evita
`runtime-evaluated-base-classes` en `pyproject.toml`, no la disciplina de quien escribe.

## Adaptadores

- Implementan un puerto y nada más. **El módulo se llama como la implementación**, no como el puerto,
  así que el par puerto/adaptador se lee en el nombre y caben dos implementaciones sin renombrar nada.
- **El programa no importa nada de `skills/`.** Es autocontenido: lanza los procesos el mismo por su
  puerto y valida lo que recibe con sus propios modelos. **Acoplar el flujo nuevo al viejo para ahorrar
  duplicación sale más caro que la duplicación**, así que las copias que eso genera se declaran y se
  miden con un contrato en vez de eliminarse.
- **Lo que define a un agente invocado viaja junto, en un objeto.** La rúbrica, sus herramientas y los
  directorios que puede leer son un value object que construye la frontera y el entrypoint inyecta, no
  tres cosas repartidas por capas: repartidas, nada obliga a que cuadren, y una rúbrica puede acabar
  ordenando cargar lo que el agente no puede leer sin que el veredicto lo delate. **Un puerto para un
  valor constante es indirección; un invariante entre varios valores pide un objeto.**
- **El texto de la rúbrica del juez y la metodologia del implementador se quedan en infraestructura**, no
  en una factoria de aplicación: el prompt es lo que se le manda a **un ejecutable concreto** por su
  entrada estándar, con su esquema y sus flags, y cambia con la receta medida contra ese ejecutable. Que
  la capa que conoce el harness sea la misma que redacta lo que el harness recibe es lo que evita que
  aplicación tenga opinion sobre el transporte.

  **Y cada una tiene un solo sitio donde vive.** Un `.md` que repita la rúbrica o la metodologia es una
  segunda copia que nadie compara, y el programa **no lee `.md` de agente**.
- **Lo que no cambia entre invocaciones es constante; los datos de la slice los compone la invocación.**
  **Aplicación no compone texto de prompt**: pasa objetos del dominio y es la frontera la que decide
  como se escriben. Y un prompt **abre con el dato y cierra con las instrucciones**: el dato largo delante
  y lo que se pide detras es como lee mejor el modelo. Cada bloque de dato va en su propia etiqueta, y la
  etiqueta repite en la apertura y en el cierre un identificador derivado de su contenido: eso es lo que
  evita que un delimitador tenga que sobrevivir a su propio contenido.

  **La forma de una lista se extrae cuando deja de ser un parecido y pasa a ser invariante.** Cada
  prompt es un contrato con un agente distinto y nada exige que se parezcan, así que compartir la forma
  entre dos puede ser coincidencia; cuando la repite un consumidor más, ya no lo es. **Y una condición
  así, escrita, se ejecuta cuando se cumple**: la que nadie ejecuta ensena que este fichero es opinion.
- **Un invocador que no tiene issue delante no llena los mismos campos que el conductor**, así que la
  rúbrica **describe la carga en vez de prometerla llena**: dice que los campos viajan siempre, que
  pueden venir vacíos y que un campo vacío es un insumo que no ha llegado -que el agente reporta como
  falta de dato, no como item conforme-. Lo que **no** se hace es escribir que esos insumos no existen.
  Y los campos entran **sin default**, que es lo que obliga a llenarlos en vez de heredar el vacío en
  silencio.
- **Una fuente declarada viaja con su contenido citado por su ruta, y quien lo lee es un adaptador
  compartido, no cada invocación por su cuenta.** Es la misma regla de la lista que deja de ser parecido
  y pasa a ser invariante, aplicada a lo que citan.
- **Lo que vive bajo el worktree se lee por el puerto de proceso, nunca abriendolo por nuestra cuenta.**
  Es la única costura documentada del entrypoint: un worktree de test no es un directorio real en disco,
  y toda la suite que lo dobla asume que leerlo pasa por ese puerto. Los adaptadores que leen la raíz de
  configuración de la maquina son otra familia y si abren ficheros.
- **La raíz de configuración de la herramienta la resuelve un objeto propio** (la variable de entorno si
  está puesta, o la raíz por omisión expandida, con la variable vacía tratada como ausente). La comparte
  todo adaptador que necesite saber donde vive esa configuración, porque lo que comparten no es una regla
  del programa sino **la convención de la herramienta**.
- **Un adaptador que escribe a disco fuera del camino de error no captura su `OSError`.** Sale del
  programa sin mapear, aunque eso colapse con un código de salida que significa otra cosa. Se acepta
  porque la alternativa es peor: **decidir aquí que hacer con el fallo de escritura sería inventar una
  política que ningún criterio pidió**, y un adaptador que decide política es antipatrón declarado de esta
  misma capa. Cuando se cierre, se cierra **decidiendo la política**, no capturando el `OSError` a
  escondidas.
- **El rastro de una llamada lo escribe la capa que ve la respuesta, no la que orquesta**, y se anexa
  **antes** de entrar en el bloque que la mide: una llamada que muere dentro de ese bloque es justo la
  conversación que se quiere leer, y en aplicación no queda nada de ella.

  Consecuencia aceptada: una respuesta que **no** parsea no deja rastro -no hay identificador que
  escribir-. Por eso el identificador de sesión es campo **obligatorio** y no opcional: una llamada sin
  identificador no se puede volver a encontrar, que es el fallo que este rastro existe para cerrar.
- **Los almacenes durables viven bajo un mismo directorio y un mismo patrón de nombre**, para que un solo
  criterio contesta "donde vive esto".

  **Un almacen se parte en ficheros hermanos cuando lo que pesa y lo que se consulta a menudo no son lo
  mismo**, unidos por una clave y un sello para poder juntarlos. Sin eso, contar lo ligero obliga a leer
  lo pesado.

  **Los payloads de un almacen durable declaran su esquema**, reusando el mismo emisor plano que los que
  viajan en un prompt. Es lo que deja preguntar que campos trae una fila sin abrir el fichero.
- **Lo que además se mira en vivo se escribe dos veces desde el mismo adaptador**, no desde dos
  compositores: una vez a disco, porque es la que dura, y una vez a la salida de error, porque es la que
  deja mirar un run en marcha. Las dos comparten el mismo payload, compuesto una sola vez.
- **Un turno del arnés no se anexa a un almacen durable propio.** Lo que un turno dice -numero, herramienta
  y objetivo- ya lo escribe el registro de usos de herramienta al terminar cada llamada; anexarlo tambien
  por turno seria escribir la misma fila dos veces con otro nombre.

  **Toda fila de todo almacen durable trae marca de tiempo, repo, issue y la slice a la que pertenece.**
  Las cuatro se declaran una sola vez -en `StampedRow`, que los payloads heredan- y se escriben siempre
  juntas a traves de un unico constructor (`_stamped`), nunca sueltas campo a campo. Cruzar dos almacenes
  por sesion para saber de que slice era una llamada es la arqueologia que esto reemplaza. El texto que
  nombra la slice sale de `SliceIdentity`/`CanonicalSliceId`, nunca compuesto a mano en un payload: **el
  formato del identificador -el prefijo, el `-NN` final- vive en un solo sitio**, y las cuatro coordenadas
  son siempre obligatorias: ningun payload las redeclara opcionales para tolerar una fila que no las traiga.
- **El registro durable lo escribe el programa el mismo**, con el mismo patrón que los demas almacenes y
  un payload de frontera que traduce el dominio a las claves del log. **No delega esa escritura en un
  script fuera de su paquete**: sería una dependencia fisica con código que no es referencia.

  **El lado que relee el log es el mismo modelo que lo escribe, y sus claves y sus valores salen en el
  idioma del código.** No hay `AliasChoices` ni traduccion de un vocabulario anterior: un contrato que
  fijamos nosotros no tiene nada que traducir. Una fila de una generacion anterior -de cuando el log
  hablaba castellano, o de cuando una coordenada podia faltar- no se lee a medias: falla con un error que
  nombra que esa fila no es de esta generacion, en vez de devolver un registro con la mitad de los campos
  a cero. El histórico de esas filas se archiva aparte; este programa no lo interpreta.
- **Un registro que debe tolerar que un value object crezca no nombra sus campos.** La regla general
  existe para que un contrato que cambia de forma rompa donde se declara; aquí se invierte a propósito
  cuando el criterio que trajo la fila pide justo lo contrario: que añadir un campo no obligue a tocar el
  registro. Nombrar cada campo volvería a acoplar la fila durable a la forma exacta de ese value object.
- **El programa no escribe ningún número que no venga del harness.** Hay puerto de reloj, pero lo que ese
  reloj lee es del programa y no de lo que la llamada costó. De ahi que el gasto sea un value object que
  distingue "todavía no se ha medido nada" de "cero medido": con nada medido, la clave no se escribe.

  **Y todas las llamadas cuentan, también las que acaban en excepción** -si no, una fila con varios
  descartes escribiria un coste sistematicamente por debajo-: una vez parseada la respuesta, el gasto
  cuelga de cualquier error medido que salga del bloque, y solo esta capa puede hacerlo porque es la
  única que la ve. Si no llegó a parsearse no hay nada que colgar: eso es "no medido", no un cero.

  **El gasto sobrevive a la invocación**: se acumula por invocación pero se siembra con lo que trae el
  estado persistido y se escribe de vuelta en cada paso que lo cambia, así que una slice reinvocada sigue
  viendo su presupuesto entero y la fila que cierra el run suma todas las invocaciones.
- Un código de salida distinto de cero **es un dato**, no una excepción: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo está en `stderr` y una excepción lo borra.

  **Pero un código que no distingue los casos no clasifica nada por si solo: entonces se clasifica la
  salida.** Cuando una herramienta sale distinto de cero para varios estados que hay que separar, el
  código es un dato que no dice nada y el único que decide es `stdout`.

  **Y un código distinto de cero con `stderr` no vacío es el propio comando fallando**, que se distingue
  de una respuesta que si llegó pero no se pudo interpretar. Son dos causas y llevan excepción distinta,
  las dos del **dominio** -aplicación las captura, así que tienen que vivir donde pueda importarlas- y
  las dos traducidas al miembro del vocabulario que dice cual fue. **Esto no es permiso general para
  propagar cualquier fallo de lectura**: el vocabulario sigue teniendo miembros para lo que se clasifica
  sin ambiguedad y sin excepción, y esos siguen sin motivo porque no son un fallo, son una lectura
  valida. Lo que gana la clasificación es un porque que un `except` genérico fundiria en un valor mudo.
- **Dos adaptadores de la misma herramienta comparten su excepción**, que vive donde la necesito el
  primero que la tuvo: es el mismo fallo -un comando de esa herramienta que sale mal- y el acoplamiento
  declarado sale más barato que una tercera copia. Su casa natural es un módulo de frontera compartido, y
  se hace cuando exista un tercer adaptador de esa herramienta.
- **Ninguna llamada a un proceso externo se lanza sin tope, y el tope no lo elige el adaptador.** El
  adaptador recibe el presupuesto por constructor y lo pasa como `timeout`; el número y su motivo viven
  en `docs/conventions/domain.md`, que es lo que separa "aplicar un tope" -trabajo de esta capa- de
  "decidir cual" -política, y por eso el constructor **no tiene default**: un adaptador de proceso sin
  presupuesto no compila-. Como el programa entero lanza procesos por ese puerto y **solo** por el, el
  tope se aplica en un sitio y no hay adaptador que se lo salte.

  Al agotarse se **falla en cerrado**: se mata al hijo y el adaptador traduce el timeout a su excepción
  -que vive con el puerto, por el motivo de `docs/conventions/architecture.md`-. Lo que el proceso
  hubiera escrito ya **se descarta**: media respuesta no es una respuesta. No hay reintento aquí:
  reintentar es política, y esta capa no la decide.
- **Dos campos que tienen que concordar dejan representable el estado que no debe existir; uno solo lo
  hace imposible.** Cuando una bandera dice lo mismo que la no-vacuidad de un dato, la bandera se retira
  y se deriva: así una invocación que muera a medias no puede reanudar afirmando algo que no tiene.
- **El cuerpo de la pull request lo compone un modelo de frontera**, que fija sus encabezados y su orden.
  Se quedan en castellano: son **contenido del artefacto que lee una persona**, en el idioma del issue,
  no identificadores.

  **La pull request nace lista para revisar, y eso no afloja el control humano.** Lo que hace que el
  merge lo decida una persona es que el programa **no mergea**: se para y termina. Un borrador no añade
  esa garantía y si añade un paso manual que nada recuerda.
  - **Se asigna a quien esta autenticado**, que es quien conduce el run y quien tiene que mergear. Se
    declara con la forma que resuelve la herramienta en la misma llamada, no preguntando antes quien
    eres: una llamada que se puede ahorrar es una llamada que puede fallar.
  - **El commit acredita como co-autor al harness que escribió el código**, en un objeto de frontera
    propio y no como una cadena pegada al título, porque el **asunto** del commit y el **título** de la
    pull request dejan de ser lo mismo en cuanto uno de los dos crece. Lo que **no** se hace es anadirlo
    como asignado: solo se puede asignar a colaboradores del repo, así que sería una llamada que falla o
    se ignora en silencio.

  Estas decisiones sobre el cuerpo **no tienen test de contrato**: no hay vocabulario que extraer de un
  cuerpo en prosa, así que estos párrafos son lo único que las sostiene.

  1. **La referencia que cierra el issue depende del formato**, no de la costumbre: con una subissue por
     slice la pull request si cierra su issue y la plataforma lo hace sola al fusionar; con un issue por
     feature entera eso sería mentira.
  2. **Confirma que los criterios se cumplieron en vez de reproducirlos.** Reproducirlos le da a quien
     revisa lo que ya sabe -los declara la subissue- y le quita el sitio al *por que*, que es todo el
     trabajo de este cuerpo. Y **donde vive cada test** el programa no lo sabe: el informe del
     implementador trae rutas con su tipo, no un mapa de criterio a test, así que escribirlo sería
     inventarlo.
  3. **La deuda aceptada es lo que el implementador declaró haber dejado fuera, junto a los hallazgos que
     sobrevivieron a la vuelta con la que el juez dejó pasar la slice.** Llegan como lista y se
     transportan sin adivinar donde corta una frase; una lista vacía significa "nada quedó fuera", y la
     sección solo se emite cuando trae bullets. Los de vueltas anteriores **no** entran: pueden haberse
     corregido después, y darlos por aceptados sería mentir.

  **La intención inferida se declara en el encabezado.** Cuando la subissue no la trae, el encabezado lo
  dice; cuando la trae, va plano. La decisión es del **formato**, y por eso vive en el modelo y no en
  quien conduce: el dato -declarada o no- ya viaja en lo que le llega. Lo que el programa **no** hace es
  inventarse la prosa que falta: presentar como intención algo que nadie escribió es justo lo que ese
  encabezado existe para impedir.

## Entrypoints

- Una clase, con `main` como `@classmethod`, que el módulo ejecutable invoca y que `[project.scripts]`
  declara como el ejecutable instalado.
- **Es el único sitio que monta el grafo de dependencias**: elige los adaptadores concretos y los
  inyecta. No hay contenedor de inyección: hay un adaptador por puerto, y la costura de test la da el
  constructor. El grafo entero del conductor se monta sobre **un solo** puerto de proceso, que es también
  la única costura que necesita su test: doblarlo basta para conducir un run sin tocar ninguna
  herramienta externa, y lo que el run hizo o no hizo se lee en el `argv` que recibio.
- **Mapea las excepciones tipadas del dominio a códigos de salida**, con `IntEnum`. La respuesta va a
  `stderr` y el resultado a `stdout`, siempre separados: hay tests que comprueban que un fallo no
  escribe nada en `stdout`.
- Los códigos de salida son contrato con quien invoca el programa: **el `IntEnum` es su única
  fuente**, se anaden al final y no se reordenan.
- **Un código por decisión de quien invoca, no uno por excepción.** La vara para decidir si hace falta
  uno nuevo es: ¿que hace distinto quien lo recibe? Todo lo que significa "el mundo fallo, el estado
  persistido sigue bueno" comparte uno solo, y no se parte por clase de excepción. Una llamada muerta en
  su tope si lleva el suyo, porque reinvocarla a ciegas volvería a pagar el tope entero.

  **Y se mapea donde el puerto de proceso se inyecta por constructor**, no en `main`: arriba quedaría sin
  costura con la que probarlo.

  **Cuando el reparto pasa del tope de `return` que mide el linter, va en un `match` en un sitio** en vez
  de en una cadena de `except`, y **la rama genérica es la de "el mundo fallo, el estado sigue bueno" a
  propósito**, que es literalmente la regla de arriba. Lo que puede llegar se acota, y lo que no este ahi
  sigue saliendo sin capturar.
- **La proyección del dominio al código de salida es un `match` exhaustivo sin rama genérica**: un
  miembro nuevo rompe en `mypy` en vez de caer en un valor por omisión. Una rama que no se puede
  alcanzar se agrupa con el lado fail-closed.
- **Una invocación que el parser rechaza sale con su código de uso, y `--help` con el de exito.**
  `argparse` levanta `SystemExit(2)` para las dos cosas, y ese `2` puede estar reservado a otra cosa en
  el contrato: hay que traducir ese `SystemExit` mirando su código, que es la única forma de distinguir
  la ayuda del error de uso sin reescribir `argparse`.

## Antipatrones

- Un `cast` en la frontera.
- Un modelo de frontera sin `extra="forbid"`.
- `strict=True` a nivel de modelo.
- Un helper de mapeo en el caso de uso en vez de en el modelo.
- Un `ValidationError` de Pydantic saliendo de la capa.
- Un adaptador que decide política -reintentos, presupuestos, que hacer con un fallo-.
- Una llamada a un proceso externo sin tope, o un adaptador que elige el suyo.
- Un esquema que viaja en un prompt con más de un campo.
