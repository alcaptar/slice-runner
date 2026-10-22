# Capa de dominio

Value objects, puertos y excepciones. No conoce ninguna otra capa, no hace entrada/salida y no lleva
Pydantic.

## Value objects

- **Dataclasses `frozen=True, kw_only=True, slots=True`.** Sin excepciones: lo que se construia por
  partes y luego se mutaba, se construye una vez al final o se rehace con `dataclasses.replace`.
- Sin sufijo `VO` ni `ValueObject`.
- Datos y, si hace falta, comportamiento propio. **Nada de serialización**: convertir a las claves de
  un contrato externo es trabajo de la frontera (`docs/conventions/infrastructure.md`).

## Vocabulario cerrado

**`StrEnum`**, no tuplas de `str`. Los miembros se serializan como su cadena, así que ni el formato del
issue ni el JSON de salida cambian, pero las comparaciones y los `choices` de cada interfaz de línea de
comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un contrato**
  que lo fije de otra forma.
- En `argparse`, `choices=[str(x) for x in Enum]`: con `list(Enum)` el mensaje de error muestra el
  `repr` del miembro.
- Códigos de salida de un ejecutable: `IntEnum`, y el mapeo desde el vocabulario del dominio con un
  `match` exhaustivo, para que añadir un miembro rompa en `mypy` en vez de caer en silencio en la
  rama genérica.
- **Un puerto contesta con el vocabulario, no con un `bool` derivado de el.** Un booleano colapsa
  estados que se arreglan distinto, y quien lo consume no puede separarlos: el que decía si algo estaba
  fusionado fundia "cerrado sin fusionar" con "todavía abierto", y quien conducia el run tickeaba el tope
  entero esperando algo que ya no podía llegar. **Y si la misma llamada ya distingue las dos cosas, eso no
  es un segundo puerto ni una segunda llamada: es un campo más de una respuesta que ya se estaba
  leyendo.** La traducción desde las cadenas de la herramienta vive en la frontera.
- **Un estado ausente es un miembro del vocabulario, no un `| None`.** El caso "aquí no hay valor" se
  declara dentro del enum, con valor `None`, y para poder llevarlo el enum deja de ser `StrEnum` y pasa a
  `Enum` plano. Así el dominio nunca ve `None`, y la frontera entra y sale con la construcción normal del
  enum -`Enum(valor)` al entrar, `miembro.value` al salir- en vez de con una rama defensiva en cada sitio
  que lo toca.

  ```python
  # ejemplo/domain/{vocabulario}.py
  class {Vocabulario}(Enum):
      EMPTY = None
      {UN_CASO} = "{un-caso}"
  ```

  Un `| None` cuyo vacío solo es legal según lo que valga otro campo no es un ausente: es un vocabulario
  partido en dos, y lo gobierna la regla de los dos campos que tienen que concordar
  (`docs/conventions/infrastructure.md`).
- **La pertenencia se pregunta contra los valores, no con `in`.** En la versión mínima de Python que
  declara `docs/conventions/architecture.md`, un `nombre in cls` con una cadena que no es miembro lanza
  `TypeError`, así que una guarda no puede romper por la forma de preguntar justo cuando el valor es uno
  cualquiera.
- **Un vocabulario que también exista en código que no es referencia se declara y se mide con un
  contrato, nunca se comparte por import** (ver `docs/conventions/infrastructure.md`). Su traductor vive
  **del lado del destino**, con `match` exhaustivo y sin rama genérica, para que la regla no acabe siendo
  un `if` de quien orquesta, y para que añadir un miembro sin proyectarlo ponga `make check` en rojo en
  vez de caer en una rama por omisión.

## Puertos

- Interfaces con `ABC` y `@abstractmethod`. Nada más: sin implementación por defecto, sin estado.
- El puerto declara lo que el dominio necesita, no lo que el adaptador sabe hacer.

## Politica: la lógica pura vive aquí, no en aplicación

Lo que es **regla exacta** -que paso viene después de un resultado, cuando se agota un presupuesto- es
un objeto del dominio, no prosa de una skill ni un `if` en un caso de uso. Forma: dataclass frozen con
**su configuración inyectada**, sin entrada/salida y sin conocer a nadie. La configuración es un value
object normal: lo construye el entrypoint y entra como dato (ver `docs/conventions/application.md`).

- **Total o explícita**: un par de entrada que la política no describe **lanza** su excepción, no cae en
  una rama genérica, para que se vea en el momento y no se confunda con "no pasa nada".
- **Devuelve un value object con el efecto entero**, no un booleano ni un `dict`: el paso siguiente, el
  estado en que queda y cuanto hay que esperar viajan juntos. Un consumidor que tuviera que recomponer eso
  volvería a tener política repartida.
- **Se cubre desde fuera**, como todo el dominio: la tabla de entradas y salidas entra por el subcomando
  que la expone. No hay tests unitarios de dominio (`docs/conventions/testing.md`).

**Cuando ningún tick arregla algo, cero ticks es la cuenta correcta**: se cierra directo en vez de gastar
la ventana de gracia de una espera que no puede terminar bien. Y **la pregunta de más solo se paga cuando
la primera lectura salió ambigua**: quien produce esa distinción es quien orquesta, no la política, porque
una lectura que no separa dos casos no sabe cual tiene delante.

**La higiene del índice es política.** Compara lo que hay en el índice con lo que el implementador
declaró y devuelve las ofensas; la tupla vacía es el índice limpio. Las decisiones que no son deriva:

- **Dos causas que no se arreglan igual no comparten contador.** Un control rojo es código que falla y lo
  puede arreglar otra vuelta del implementador; un rechazo de higiene es un informe incompleto -toco
  ficheros que no declaró- y no dice nada sobre si el código está bien. Por eso lleva resultado propio,
  contador propio y presupuesto propio, y agotarlo cierra el run con un estado que nombra la higiene.
- **Fail-closed sin rama especial.** Sin nada declarado, todo lo que este en el índice cae en la ofensa
  general, que es lo que sale solo de la regla. Y **"nada staged" no es asunto de esta política**: eso ya
  lo dice quien va a leer el diff, y reimplementarlo aquí sería un segundo sitio donde decidir lo mismo.

Las decisiones sobre los presupuestos tampoco son deriva, y están aquí para que no se "arreglen" hacía el
lado fácil. **Los valores concretos viven en el value object de configuración, y de donde sale cada uno
está en las pull requests que los fijaron**: aquí va la regla que los gobierna, no la medición que los fijo.

- **Un número por concepto, no uno por caso.** Una sola separación mínima entre ticks para todas las
  esperas, un solo tope para todas las clases de llamada a un proceso externo. Partirlos por caso serían
  números que nadie ha medido, y un número sin medición no es una regla: es una preferencia. Consecuencia
  aceptada a propósito: mover uno mueve todo lo que lo comparte.
- **El tope de espera acota la invocación, no el run.** Agotarlo **no cierra** nada: deja el run abierto y
  persistido en su paso, diciendo que reinvocar es justo lo que toca.
- **La espera tiene un tope por clase de espera, y eso no rompe el bullet de arriba: lo aplica.** Esperar
  a una maquina y esperar a una persona **no son el mismo concepto**, aunque los dos se midan en segundos.
  A la maquina se la espera porque **esta trabajando**, y su tope existe para cazarla **colgada**: pasado
  el suyo, el número ya no dice "ten paciencia" sino "algo va mal". A una persona se la espera porque
  **está en otra cosa**, y ahi no hay nada que cazar: una respuesta que tarda media mañana es el flujo
  funcionando, no una anomalia. Un solo número obliga a elegir entre no detectar nunca una espera colgada
  y cerrar runs sanos porque alguien no estaba delante.
- **Y el contador se reinicia en cada paso, que es lo que hace honestos a esos topes.** Con un acumulador
  único para todo el run, **el último que espera paga lo que gastaron los demas**, y cuanto le queda
  depende de lo que una persona haya tardado antes: el tope dice una cosa y entrega otra. Un tope que solo
  se cumple si nadie se entretiene aguas arriba no acota nada.
- **El tope por llamada vive con los demas números aunque quien lo aplique sea un adaptador**, porque es
  el mismo tipo de dato: un número medido con el que se acota una espera. Tenerlo aquí es lo que evita que
  cada adaptador se invente el suyo.
- **El descarte de una llamada al arnés no gasta reintento en ninguno de los pasos que la hacen.** Donde
  no se ha tocado el código es evidente; donde si, la llamada rota pudo dejar cambios sin comitear pero
  nada de eso llega al índice -un informe que no se puede leer nunca llega al paso que staggea-, así que
  tampoco es un intento de la fase que un control o un juez lleguen a medir. Quien lo acota es la
  pregunta del coste, que **si** cierra, con el estado que corresponda a lo que impidio seguir. Darle contador propio sería inventar una política que ninguna
  medición sostiene; dejarlo sin ningún cierre sería un bucle que paga una llamada por vuelta y no termina.
- **El presupuesto de coste impide la siguiente llamada; no tira la que ya se pago.** Un veredicto que
  aprueba nunca se convierte en agotado -entregar no cuesta harness-, y la llamada siguiente se corta
  **antes** de invocar, no después de pagarla. Las dos comprobaciones conviven a propósito: la de después
  cierra el bucle de descartes, la de antes es la que impide tirar una aprobación.
- **La pregunta del coste se hace por llamada, no por el agregado**, y esa firma es load-bearing: se mira
  primero si **esa** llamada dejó medición y solo después se suma. Al agregado se le puede preguntar
  eternamente sin que conteste que no, porque lo que no se mide no suma.
- **Un gasto no medido cierra el run, y con estado propio.** Lo que no se puede sumar no se puede
  acotar, así que la pregunta del coste contesta que no se sigue: es la misma elección fail-closed que
  una lectura indeterminada, y el precio del falso positivo es una reinvocación mientras el del falso
  negativo es el bucle que el tope existe para cortar. Lo que **no** puede contestar es agotado: no
  poder medir y haberse pasado del tope son causas distintas, se reparan en sitios distintos, y
  colapsarlas manda a diagnosticar el dinero cuando el problema estaba en la respuesta. Por eso la
  pregunta devuelve **cual** de las cosas ocurre y no un booleano, y por eso reabrir por una llamada no
  medida conserva lo gastado: lo que fallo no fue el presupuesto.
- **Lo que se cuenta son todas las llamadas del run.** Contar solo una parte abarataria el número a costa
  de dejar sin cierre el bucle del descarte.

## Excepciones

- Nombradas por lo que pasa, no por donde.
- El catalogo es el de las excepciones **del dominio**. Un puerto que solo consume la infraestructura
  lleva la suya con el, declarado con su motivo en `docs/conventions/architecture.md`.
- Jerarquia cuando el consumidor necesita distinguir: se hereda de una comun cuando la interfaz de línea
  de comandos les da códigos de salida distintos, y quien no distingue captura la de arriba.
- Heredan del tipo que corresponde (`ValueError`, `OSError`), no de `Exception` a secas.

## Nada de `dict` crudo como valor de retorno de lógica

Un `dict` que cruza dos funciones propias se lee con `.get()` en el consumidor, y ahi una clave mal
escrita y una ausente dan lo mismo. Los `dict[str, object]` que quedan son todos frontera de
serialización, con la excepción declarada de un registro durable que debe tolerar que un value object
crezca (`docs/conventions/infrastructure.md`): reconstruirlo aquí rompería con cualquier clave añadida,
renombrada o ausente entre versiones, y ninguna lógica lo destructura.

## Antipatrones

- Un dataclass del dominio sin `frozen=True, kw_only=True, slots=True`.
- Un `to_dict()` en el dominio. **La traducción al contrato externo vive en la frontera.**
- Una tupla de `str` como vocabulario cerrado.
- Un `Enum | None` -o `Optional[Enum]`- cuando lo que se modela es un estado ausente: eso es un miembro
  más del enum, con valor `None`.
- Un `Enum | None` cuyo vacío depende de lo que valga otro campo: eso es un vocabulario partido en dos.
- Un `dict` como valor de retorno de una función de lógica.
- Pydantic en cualquier fichero de `domain/`.
