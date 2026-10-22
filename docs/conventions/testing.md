# Tests

## Como se mide todo

```bash
make check   # ruff check + ruff format + mypy strict + pytest; todo verde
```

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`.

**Lanzalo siempre con `uv`.** El programa depende de terceros, así que un `python3 -m pytest` con el
interprete del sistema pasa o falla según lo que tengas instalado, y eso no es una vara.

Para acortar el ciclo:

```bash
make test PYTEST_ARGS="--nf -x --tb=short --disable-warnings --color=no --no-header"
```

## Lo externo se dobla, y se dobla dos veces

**Ningún test lanza un proceso, abre un pseudoterminal ni deja pasar una llamada a la herramienta de
verdad.** Lo que depende de la máquina -su carga, lo que tiene instalado, lo que tarda en arrancar un
hijo- no es una vara: un test que falla porque la máquina va cargada bloquea a quien no ha roto nada.
Escribir en `tmp_path` no es lo externo: es el sistema de ficheros del propio test.

Lo externo se corta con **doble inyección**:

- **El adaptador recibe por constructor el puerto de lo externo**, y su test le pasa un doble y comprueba
  la interacción: qué se le pidió y cómo se traduce lo que contesta, sea una salida, un código distinto de
  cero o un fallo.
- **La pieza del borde recibe por constructor la librería externa misma**, y su test la dobla con
  `create_autospec(..., spec_set=True)` y comprueba la llamada: con qué argumentos y con qué tope, y a
  qué excepción propia se traduce cada fallo de la librería.
- **El test de integración monta la aplicación entera de verdad y corta solo lo externo**, inyectando el
  doble donde el entrypoint monta el puerto. Todo lo propio que hay en medio -casos de uso, adaptadores,
  modelos de frontera- es real.

```python
# ejemplo/infrastructure/local_{cosa}.py
class Local{Cosa}({Cosa}):
    def __init__(self, *, budgets: Budgets, {libreria}: {TipoDeLaLibreria}) -> None: ...


# ejemplo/tests/infrastructure/test_local_{cosa}.py
class Test{UnFalloDeLaLibreria}:
    def test_{se_traduce_a_la_excepcion_propia}(self) -> None:
        {libreria} = create_autospec({libreria_real}, spec_set=True)
```

- **El paso directo al sistema operativo no tiene test**, y por eso no tiene ni una decisión dentro: es
  lo que el entrypoint inyecta en la pieza del borde, y el tope, la traducción de errores y la lectura de
  la salida viven en la pieza que lo recibe, que sí se prueba. Que el tope y la muerte del hijo siguen en
  su sitio se vigila escaneando el árbol, no ejecutándolo.
- **La única excepción es un artefacto que solo se comprueba ejecutándolo**: un script de shell, el
  paquete construido. Su test se aparta de la suite que corre en cada vuelta de una slice, y lo corre la
  integración continua. No vale para código del programa: si para probarlo hay que ejecutarlo, le falta
  la costura.

## Los dos árboles, y por que

| | Que cubre |
|---|---|
| Dentro del paquete | El programa. Co-localizado, espejando las capas. |
| `tests/` en la raíz | Los scripts de `skills/` y los contratos que no tienen paquete donde vivir: entre el programa y su documentación, entre dos vocabularios del propio dominio, y los invariantes que escanean el árbol. |

**Lo que comparten los dos árboles vive dentro del paquete**, no en la raíz, porque `src` entra en el
`pythonpath` y el directorio de `conftest` no: el árbol de dentro no puede consumir del de fuera y al
reves si.

**Lo compartido por la suite de la raíz vive en su `conftest.py`.** No vuelvas a definir un helper en un
fichero de tests: con varias copias de firmas distintas, leer cualquier test obliga a subir a la cabecera.

## Forma de un test

- **Dentro de una clase**, agrupados por el comportamiento que fijan. Nunca funciones sueltas en el
  árbol nuevo.
- **Cero prosa**, igual que el código de producción: el nombre del test es la frase.
- El nombre dice **que se garantiza y por que**, no que metodo se llama:
  `test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null`.
- Los helpers de un test son `@staticmethod` de su clase de test, o viven en un módulo compartido, pero
  **nunca sueltos a nivel de módulo**.
- **Lo que comparten varias clases de test del mismo módulo vive en una clase de ese módulo que esas
  clases heredan**, no en una función suelta ni en un módulo compartido que solo se importa desde un
  sitio. Cubre tanto un helper como un `@pytest.fixture(autouse=True)` que solo protege a esas clases, y
  es lo que hace que la regla de arriba no tenga hueco: un helper de dos clases del mismo fichero no
  tiene por que salir del fichero.

  ```python
  # ejemplo/tests/test_{cosa}.py
  class {LoQueComparten}:
      @staticmethod
      def _{helper}() -> None: ...


  class Test{UnComportamiento}({LoQueComparten}): ...
  ```
- **En un fixture `autouse`, donde se declara es su alcance, y eso decide donde va.** Dentro de la clase
  cuando protege a esa clase; en la clase que se hereda cuando protege a un grupo; **a nivel de módulo
  cuando lo que protege es que ningún test del fichero toque algo de la maquina de quien lo corre**. Ese
  último caso es el único en el que un `def` a nivel de módulo es correcto en el árbol de test: bajarlo a
  una clase le recorta el alcance en silencio, y el mecanismo que lo sustituiria -que cada clase nueva se
  acuerde de heredar- falla sin avisar justo en la que se olvide.

## Object Mothers

**Los objetos de un test los construye un mother**, no el propio test:
`{paquete}/tests/mothers/{cosa}_mother.py`.

Un mother da defaults sensatos y deja que cada test nombre **solo lo que su caso cambia**, que es lo que
hace legible el assert. Sin ellos, el mismo objeto se copia en dos ficheros con valores distintos y
ninguno dice por que.

Los metodos son **escenarios con nombre**, no un `create(...)` con todo por defecto: así el test dice de
que caso va sin leer los argumentos.

## Payloads grabados

`{paquete}/tests/payloads/` son respuestas de llamadas **reales** guardadas tal como llegaron. Es lo que hace que
el test de frontera mida la carga literal en vez de un modelo nuestro de ella, y de ahi salen datos que
nadie escribiria a mano.

**Cuando cambia el contrato del contenido, se reescribe a mano el campo afectado -en todas las copias que
el otro lado escriba- en vez de regrabar.** Es divergencia declarada de "grabados", y el motivo es que no
hay nada que grabar: ninguna llamada vieja puede traer el campo con la forma nueva, y regrabar arrastraria
de paso el resto de la respuesta, que es justo lo que otros tests fijan. Lo que **no** autoriza es tocar
la respuesta: si lo que cambia es una clave del otro lado, hay que regrabar, porque ahi la forma real es
lo único que se esta midiendo.

## Dobles

- **`create_autospec(X, spec_set=True, instance=True)`** para puertos sin estado.
- **Dobles con estado a mano** cuando el test necesita preguntar por lo que se le paso: un `Mock` no
  sirve para eso.
- **Un doble dobla lo que su nombre dice y nada más.** Si un solo puerto sirve a dos consumidores, cada
  uno tiene su respuesta: un doble que respondiera a cualquier entrada con la respuesta del otro haría que
  el test pasara o fallara por el motivo equivocado. Lo que no hace nunca es dejar pasar a uno de los dos
  a la herramienta de verdad.
- **El doble de una conversación entera contesta por lo que se le pide, no por orden.** Devolver salidas
  en el orden en que se pasaron sirve para **un** adaptador, donde el orden es parte de lo que se mide;
  en un flujo que pasa por varias herramientas el orden es detalle de implementación, así que el doble
  responde según la petición y **lanza cuando nadie escribió respuesta** para ella. Eso es lo que
  convierte "no repite el trabajo ya hecho" en algo comprobable: si lo repitiera, el doble no tendría que
  contestar y el test se cae con la petición delante, en vez de pasar por casualidad.
- **El adaptador de verdad también se pide a un sitio**, cuando su configuración entra por constructor y
  **no tiene default** (ver `docs/conventions/infrastructure.md`): sin un sitio comun, cada llamada de
  test elegiria su propio presupuesto, que es la política repartida que el default existe para impedir.
- **Nada de mockear value objects**: se usan instancias reales.
- El arrange **no se construye con la pieza bajo prueba**: el estado que un adaptador va a leer se
  prepara como la respuesta del doble de lo externo, no pidiéndoselo al propio adaptador.

## Que se testea y que no

- **Outside-in, y en este orden**: primero los tests de la **capa de aplicación** con los puertos
  doblados, luego los de **infraestructura**. Lo de dentro del dominio se cubre **por ese camino**, no
  con tests propios.
- **No hay tests unitarios de dominio**, ni siquiera cuando el dominio tiene comportamiento: se comprueba
  por el camino real por el que ese comportamiento llega. La única excepción es un value object con
  validación propia que no se pueda alcanzar de otra forma. Un test que solo comprueba que un dataclass
  guarda lo que le pasas mide el lenguaje, no el código.
- **Aplicación**: puertos mockeados por constructor, y el assert sobre el **efecto observable** (que
  recibio el puerto, que devolvio el caso de uso), no sobre la llamada.
- **Frontera**: el assert es la **carga literal** que se envia o se recibe, no un modelo de ella
  reimplementado en el test. Comparar contra un modelo propio del formato es reescribir el mapeo y
  aprobarlo por construcción.
- **Antes de añadir un test, comprobar si el comportamiento ya está cubierto.** Solo entra si aporta
  una dimensión distinta.

## Los contratos que viven fuera del paquete

`make check` **también cubre los `.md`**, y esos contratos se reparten por lo que miden, no por comodidad,
para que lo que dependa de un consumidor condenado se retire sin tocar los demas. Tres reglas los
gobiernan:

- **Un contrato extrae el vocabulario de los dos lados y los compara.** Así reescribir las dos copias a
  la vez pasa y tocar solo una falla. Si editas un documento y su contrato se pone rojo, es que has movido
  una mitad: mueve la otra.
- **Un invariante que escanea el árbol vale más que dos copias de la misma prosa.** Una regla escrita solo
  para una parte del árbol no puede fallar en la otra: cuando el tope por llamada estaba escrito solo para
  los scripts, quien juzgaba el programa no tenía con que fallarlo. El alcance es "todo", así que ni el
  árbol de test ni las formas menos usadas de hacer algo quedan fuera -una vara que solo mira donde ya se
  cumple no mide nada-.
- **Una lista de excepciones nombra lo que NO cuenta, no lo que si.** Un allow-list de los casos conocidos
  no puede fallar ante uno nuevo añadido sin tratamiento; invertir el criterio -nombrar lo que se sabe que
  es inocuo, y tratar como sospechoso todo lo que el escaneo no reconoce- si. El coste es mantener esa
  lista, y lo fija un meta-test sobre una fuente sintetica: algo que el escaneo nunca ha visto cuenta como
  sin tratar por defecto, en vez de pasar en silencio.

Y hay un contrato de rutas: **toda ruta de este repo citada en un `.md` existe**. No se enlaza con
markdown, se cita en backticks, así que lo que se valida es el token, y solo entran los que empiezan por
un directorio de primer nivel. Por eso una ruta de ejemplo se escribe como **molde**, con nombres
plantilla que no apuntan a nada del árbol (ver `docs/conventions/como-se-escribe.md`).

## Capturas de una slice con diseño

Una slice que cita un diseño entrega capturas de lo que pinta, y el encargo dice dónde dejarlas y cómo
escribir su manifiesto. Lo que dice este apartado es **cómo se capturan en este repo**.

**Interfaz de terminal.** La captura la escribe el propio test de pantalla: el mismo que dibuja la vista
y la compara con su referencia, cuando recibe un directorio de capturas, deja además el HTML de lo que
dibujó, con su color de texto, su fondo y su negrita, y con el nombre de su referencia. Se lanza desde
`tui/` con `CAPTURES_DIR=<directorio de capturas> cargo test`, y sin la variable ningún test escribe
nada.

- **Una pantalla nueva o cambiada lleva su test de pantalla**, y por eso su captura: lo que no tiene test
  no se captura, y lo que no se captura no se compara con el diseño.
- **El estado de la captura es el de los datos del mother** con que se dibujó, y es lo que el manifiesto
  dice en `state`: qué pantalla, a qué anchura y con qué slices.
- **Capturar es lo último de la vuelta.** Una edición después de capturar deja una captura que ya no es
  del código, y nada lo detecta.

## Antipatrones

- Un test como función suelta en el árbol nuevo.
- Un comentario o un docstring en un test.
- Un test que lanza un proceso, abre un pseudoterminal o deja pasar una llamada a la herramienta de
  verdad, también a través de un doble que delega en ella.
- Un adaptador que construye por dentro la librería externa en vez de recibirla: no tiene costura donde
  doblarla.
- Una decisión en el paso directo al sistema operativo: lo que no se prueba sin ejecutarlo no decide
  nada.
- Construir un objeto de dominio a mano en el test cuando hay mother, o duplicar en el test las
  constantes del mother.
- Un helper de test suelto a nivel de módulo, o repetido en dos ficheros.
- Arrange construido con la pieza bajo prueba.
- Assert contra un modelo del formato reimplementado en el test, en vez de contra la carga literal.
- Un test de dominio. Lo que hay dentro se cubre desde aplicación y desde la frontera.
