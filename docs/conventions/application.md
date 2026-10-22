# Capa de aplicación

Los casos de uso. Orquestan; la lógica vive en el dominio y la entrada/salida detrás de un puerto.

## Forma de un caso de uso

- Un módulo por caso de uso, en `application/actions/`, con el nombre del caso de uso en snake_case.
- La clase **sin coletilla**: `{HacerAlgo}`, no `{HacerAlgo}UseCase` ni `{HacerAlgo}Service`.
- Metodo principal `execute(params: <Name>Params) -> <Result>`.
- `<Name>Params` -y `<Name>Result` si devuelve datos- son dataclasses frozen **en el mismo módulo**.
- Las dependencias entran por constructor, con `*` para forzar el paso por nombre.
- **Depende de puertos, nunca de adaptadores.** El caso de uso no sabe que hay un subproceso al otro
  lado, ni que el diff lo calcula `git`.

```python
# ejemplo/application/actions/{hacer_algo}.py
class {HacerAlgo}:
    def __init__(self, *, lector: {Lector}, escritor: {Escritor}, config: {Config}) -> None:
        self._lector = lector
        self._escritor = escritor
        self._config = config

    def execute(self, params: {HacerAlgo}Params) -> {Resultado}:
        ...
```

**Un value object de configuración entra como dato, no detrás de un puerto.** Es un objeto ya construido
que inyecta el entrypoint. Un puerto cuyo único metodo devuelve una constante es indirección: lo que se
gana con el objeto es que los valores que tienen que cuadrar entre si **viajen juntos** y su coherencia se
pueda comprobar en un sitio.

## Desviación declarada: agrupar dependencias cuando la lista de puertos es el trabajo

Un caso de uso puede recibir sus dependencias **agrupadas por rol** en dataclasses frozen de su propio
módulo -lo que orquesta por un lado, lo que hace entrada/salida por otro-, en vez de listarlas sueltas
como el ejemplo de arriba. Sigue entrando todo por constructor y todo por nombre; lo que cambia es que
llegan empaquetadas.

El motivo es que una firma con esa cantidad de parametros dispara `PLR0913` de `ruff`, y las dos salidas
que **no** valen son relajar la configuración del linter -mover la vara para que pase el código- y partir
la pieza en trozos que no existen por diseño sino por contar argumentos. Agrupar por rol deja la firma
legible y no esconde ninguna dependencia: siguen siendo tipos del dominio y de aplicación, y la costura
de test sigue siendo el constructor.

**La línea, para que no se amplie por precedente: lo que autoriza el agrupamiento es de que es
proporcional la lista de puertos, no cuanto mide la firma.** Cuando la lista crece con el número de
responsabilidades, la firma larga es el síntoma y la respuesta sigue siendo partir el caso de uso. Cuando
crece con **lo que ese caso de uso existe para recorrer** -dirigir un flujo de punta a punta, contestar si
todas las piezas de un sistema están en su sitio-, partirlo no quita ni un puerto: reparte la misma lista
entre dos piezas y añade una tercera que las componga. Quien agrupe tiene que poder nombrar que recorre;
si no puede nombrarlo, esta agrupando para callar al linter.

## Conducir no es ejecutar

Un caso de uso que dirige un flujo de punta a punta **invoca** sus pasos; no los ejecuta. Cada paso que
despacha entra por su propio caso de uso, y quien conduce no habla con los puertos que ese paso necesita
para hacer su trabajo.

**La línea, para que no se amplie por precedente: lo que se despacha como paso del flujo va por caso de
uso; una comprobación previa no.** Preguntar si existe lo que un paso va a necesitar, o prepararlo antes
de entrar en el bucle, puede seguir haciendose contra el puerto desde quien conduce: no es un paso, no
tiene resultado que el flujo consuma y no aparece en el estado que se persiste. La vara para dudar no es
el tamano de la llamada: **si su resultado se proyecta a un desenlace que el flujo recibe, es un paso**.

**Y traducir el resultado de un paso al vocabulario del flujo tampoco es de quien conduce**: esa
proyección vive del lado del destino (`docs/conventions/domain.md`), porque si no cada paso nuevo trae
su propio `if` al conductor y la regla acaba repartida entre los sitios que la invocan.

Lo que se gana es que el fichero que dirige el flujo no crezca con cada paso que se añade, y que un paso
se pueda medir sin montar el bucle entero.

## Dejar constancia no es conducir

**Quien decide el flujo no compone la telemetria.** El caso de uso que orquesta un proceso largo decide
**cuando** hay que dejar constancia de un paso; **como** se deja constancia -que se persiste para poder
reanudar, que estado se pública, que se emite, que fila resume el proceso al cerrarse- es de otro caso de
uso, al que invoca como a cualquiera.

La regla se aplica cuando quien orquesta tendría que **nombrar tipos de telemetria** para construirlos.
Mientras solo pase datos a un puerto, no hay nada que extraer.

- **Quien compone un registro posee las reglas de que entra en el.** Si un dato no se pudo medir, decidir
  que no entra -en vez de escribir un cero- es suyo, no de cada llamador: una regla repartida entre los
  sitios que cierran un proceso acaba escrita en unos y no en otros.
- **Un puerto compartido no se saca solo porque el registro lo use.** Quien orquesta conserva los puertos
  que necesita para lo demas; extraerlos enteros obligaría a inventar un caso de uso por cada lectura.

Lo que se gana no es tamano de fichero: es que un cambio en el registro y un cambio en el flujo dejen de
tocar la misma pieza. La medición que lo sostiene, en la pull request que lo introdujo.

## Lo que no hace

- **No traduce a formatos externos.** Devuelve objetos del dominio; quien serializa es la frontera.
- **No captura excepciones para convertirlas en códigos de salida.** Las propaga tipadas y las mapea
  el entrypoint.
- **No decide política de reintentos ni de presupuesto.** Eso es una política del dominio
  (la política con su configuración inyectada: ver `docs/conventions/domain.md`); quien conduce el run
  le pregunta y ejecuta lo que conteste. **Los contadores que no lleva son los de reintento y los de
  presupuesto de fase**: esos viajan en el `Run` de la transición y el conductor ni los suma ni los
  compara. Un contador del registro durable que suma varios de esos **no** es uno más que nadie lleve: se
  deriva de ellos.

  **Lo único que el conductor acumula por invocación es lo que nadie más ve**, y cada acumulador lleva su
  motivo escrito donde vive: lo que acota la invocación y no el run, y lo que todavía no viaja en el `Run`
  persistido. Un acumulador nuevo sin ese motivo es estado del conductor que debería estar en el `Run`.

  De los veredictos acumulados sale una **vista, no un campo**: lo que la vuelta siguiente tiene que
  arreglar son los hallazgos de la última ronda -las anteriores pueden estar ya corregidas, así que
  mandarlas al implementador sería mandarle trabajo hecho-, y esa misma vista es la que lleva el cuerpo de
  la pull request. **Lo que se escribe al cerrar no sale de este acumulador**: la fila durable pregunta al
  puerto del corpus de veredictos por las rondas de la slice entera, así que una invocación que no verificó
  nada -porque el run venía reiniciado, o porque cierra al descubrir la pull request ya fusionada- cierra
  con lo que el corpus ya tenía escrito, y no con cero.

## Escrituras y lecturas

**La carpeta es el discriminador**, no un sufijo en el nombre de la clase: `application/actions/` para
lo que muta estado, `application/queries/` para lo que solo lee. Si un caso de uso muta y además
devuelve datos, sigue siendo una action, porque lo que la clasifica es que muta, no que conteste.

**Interrogar una política del dominio no es una query.** Se le pregunta desde el entrypoint, sin pasar
por `application/`, y es deliberado: la política no tiene
puertos que orquestar, así que un caso de uso que solo reenviase la llamada sería la indirección que
rechaza el párrafo anterior. `queries/` llega con la primera lectura que **necesite un puerto** -leer el
estado del run del foro, p. ej.-, no con la primera pregunta que se le haga al dominio.

## Componer un value object del dominio si es trabajo del caso de uso

El antipatrón de más abajo -"un helper privado de mapeo en el caso de uso"- se refiere al mapeo hacía un
**contrato externo**: convertir a las claves que espera otro proceso es de la frontera, y hacerlo aquí
duplica el mapeo que el modelo de frontera ya posee. **Componer un value object del dominio a partir de
otros no es eso**, y es trabajo legitimo de un caso de uso.

Reunir procedencias distintas -lo que declara una fuente, lo que declara otra, lo que produjo la vuelta
anterior- en el dato que otro necesita **es** lo que hace el caso de uso: moverlo a una factoria de dominio
-que proyecta **una** entidad- dejaría al caso de uso reenviando una llamada, que es justo la indirección
que rechaza el apartado del value object de configuración.

La línea, para no ampliarla por precedente: si lo que se compone lleva claves de un contrato ajeno o
formato de transporte, es de la frontera; si es un objeto del dominio hecho de otros objetos del dominio,
se queda aquí.

## Antipatrones

- Un caso de uso con coletilla en la clase, en `Params`, en `Result` o en el módulo.
- Un caso de uso importando de `infrastructure/`.
- Un helper privado de mapeo (`_to_dto`) en el caso de uso. **El mapeo vive en el modelo de frontera.**
  Componer un value object del dominio a partir de otros no cuenta: ver el apartado de arriba.
- Un caso de uso que devuelve `dict`.
- Un `try/except` que traduce una excepción de dominio a un código de salida.
