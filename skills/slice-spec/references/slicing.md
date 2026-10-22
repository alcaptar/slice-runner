# Cerebro de slicing

Reference-doc de `slice-spec`. Se carga **solo cuando toca cortar** (`reference-docs` +
`context-management`): el `SKILL.md` no lo paga y el modo `validate` tampoco salvo que lo necesite.

Es la **fuente de verdad** del troceo para cualquier repo. Universal por defecto; los detalles
mecanicos (limite exacto de lineas, forma de la verificacion post-deploy) son *defaults* que un repo
puede afinar, no dogma.

## Filosofia

Cada cambio llega a produccion en la **slice mas pequena que aporta valor o reduce riesgo**. Slices
pequenas se revisan, despliegan y revierten mas rapido y con menor blast radius. El corte es
**vertical por defecto**: cada slice atraviesa las capas necesarias para entregar un cambio de
comportamiento observable, no una capa tecnica suelta que no vale nada hasta combinarse con otras.

## Criterios de validez (rasero de aceptacion)

Antes de dar una slice por buena, comprueba las cinco condiciones **y** el rasero INVEST:

1. **Reversible** — `git revert` deja el sistema coherente. Lo que "reversible" exige de mas depende
   de como se distribuye el sujeto: en un **servicio desplegado** que sustituye comportamiento vivo,
   incluye **reversible en runtime** -volver al anterior sin redeploy, con flag o expand-contract-; en un
   **programa que se instala**, volver atras es reinstalar y eso ya es reversible, asi que lo que hay que
   comprobar es otra cosa: **que lo ya escrito siga siendo legible por las dos versiones**, o que se diga
   que no lo es y que se hace con ello. Un cambio de formato en un fichero que el programa relee no es
   reversible por mucho que el binario si lo sea.
2. **Desplegable sola** — no depende de codigo no mergeado ni de un orden de despliegue concreto.
3. **Sin work in progress oculto** — no introduce clases, campos ni ramas muertas que solo cobran
   sentido en una slice futura.
4. **Aporta valor o reduce riesgo** — entrega comportamiento, prepara infraestructura, o desbloquea
   la siguiente slice.
5. **Dentro del limite de tamano** — el diff cabe en el budget (ver "Defaults universales").

**INVEST** (Bill Wake) como chequeo rapido: *Independent, Negotiable, Valuable, Estimable, Small,
Testable*. "Small + Independent + Valuable" es, en la practica, tu "desplegable sola dentro del
budget".

## Procedimiento de corte

Guia eficiente: aplica de forma autonoma los pasos 1-3 y presenta el set de slices en la lista corta
del paso 2d de `slice-spec`. El dialogo con la persona del paso 3 solo se abre si rechaza esa lista.

### 1. Walking skeleton / tracer bullet — la slice #1

La primera slice de una feature nueva es el **esqueleto andante**: la loncha mas fina de
funcionalidad real que se construye, despliega y prueba end-to-end de forma automatica. Prueba la
**arquitectura y el pipeline**, no la logica de negocio. El "tracer bullet" (Hunt & Thomas) es el
mismo concepto operativo: un disparo que atraviesa todas las capas y cuyo codigo **se queda**.

Si la feature toca arquitectura o integracion nueva, empieza siempre por aqui: el resto de slices
son incrementos que caen sobre este andamio.

### 1b. Si hay frontera, el contrato va primero — es lo que deja paralelizar

**Dispara cuando dos piezas van a hablarse y ninguna de las dos es la otra.** Hay dos familias, y la
segunda se olvida mas:

- **Frontera externa** — la comun: un endpoint, un evento que se publica o al que alguien se
  suscribe, el esquema de un mensaje, la respuesta de un servicio del que dependemos, una interfaz de
  linea de comandos, un fichero que otro proceso lee.
- **Frontera entre capas** — dentro del mismo repo, y desbloquea exactamente igual: **el puerto** que
  el dominio declara y la infraestructura implementa, el value object que cruza de una capa a otra, el
  modelo de frontera con el que se valida lo que entra, la forma del payload que un caso de uso
  devuelve. Que las dos mitades vivan en el mismo `git log` no las hace una sola pieza: siguen siendo
  dos autores distintos escribiendo contra la misma firma.

Entonces la **primera slice fija el contrato**: los nombres, los campos, sus tipos, que es
obligatorio, que pasa cuando falla, y **un test que lo fije**. Aunque detras todavia no haya logica,
y aunque el unico consumidor sea un doble.

En hexagonal el caso mas rentable es el puerto: mergeado el puerto -con su firma y sus excepciones-,
una slice escribe el adaptador contra un caso de uso doblado y otra el caso de uso contra un
adaptador doblado, **a la vez y sin verse**. Sin el, la que llegue segunda descubre que la firma que
esperaba no es la que hay.

**El motivo es el paralelismo, y es la diferencia entre una tarde y tres.** Sin contrato, quien
produce y quien consume no pueden empezar a la vez: el segundo tiene que esperar a ver que emitio el
primero, y si no espera, cada uno inventa su version y alguien reconcilia despues -que es trabajo que
no estaba en ninguna slice-. Con el contrato mergeado primero, las dos slices se escriben **contra el
mismo texto** y pueden correr en worktrees distintos el mismo rato (paso 7 del `SKILL.md`).

Es tambien lo que hace verificable a cada lado por separado: el productor se mide contra el contrato
sin montar al consumidor, y el consumidor contra un doble que cumple el contrato sin montar al
productor.

**Vara: el contrato merece slice propia si lo va a escribir contra el alguien que no es quien lo
define** -otro repo, otro equipo, otra capa, otra slice de esta misma feature, un proceso externo-,
**y ese alguien podria estar trabajando a la vez**. Las dos mitades cuentan: si nadie mas lo usa es
diseno interno, y si lo usa uno solo que ademas va detras en el orden, sacarlo a slice es ceremonia
-lo fija la slice que lo estrena-. Lo que decide no es si la frontera es externa: es **cuantos
autores distintos** escriben contra ella y **cuando**.

**Y se fija con el primer caso real, no con todos los imaginables.** Un contrato escrito para casos
que nadie ha pedido es especulacion con otro nombre, y ademas envejece antes de tener consumidor: la
slice del contrato cubre lo que la feature necesita **hoy**, y crece con la que traiga el caso nuevo.

### 2. Heuristica ordenada

Aplica la primera que funcione. Si una sola no basta para entrar en el budget, **combinala** con
otra (tipicamente vertical + horizontal). Este catalogo deriva de los *Patterns for Splitting User
Stories* (Richard Lawrence / Humanizing Work) y de SPIDR (Mike Cohn):

1. **Workflow steps** — divide por pasos del flujo. Camino feliz minimo primero, pasos opcionales
   despues.
2. **Happy path / casos borde** — el caso principal sin manejo sofisticado de errores primero; los
   bordes (validaciones, fallos, retries) en slices posteriores.
3. **Variaciones de input/datos** — soporta un tipo/formato/region primero, anade los demas despues.
4. **Reglas de negocio** — la regla por defecto primero; excepciones y calculos especiales aparte.
   (Tecnica valida: **relajar** temporalmente una regla y reimplementarla en una slice posterior.)
5. **Interfaces** (eje de SPIDR) — corta por **plataforma, navegador o dispositivo**: soporta una
   variante esta slice, las demas despues. Tambien: interfaz simple primero, enriquecida despues.
6. **CRUD** — Read antes que Create antes que Update antes que Delete, segun valor.
7. **Horizontal por capa** — cuando el vertical no cabe en una PR: infra/migracion, dominio,
   aplicacion, presentacion en PRs separadas. Ver "Aislamiento de infra". No es anti-patron: es la
   herramienta para no superar el budget cuando el vertical no entra.
8. **Esfuerzo / simple-complejo** — version hardcodeada o manual primero, automatizacion despues. O
   extrae el nucleo de complejidad como slice aparte (**major effort**: construye la infra con el
   primer caso y los demas salen casi gratis).
9. **Capacidades transversales aplazables** — performance, i18n, accesibilidad fina, **alertas y
   paneles**: slices propios cuando aporten valor, no bloqueando el core. **Ojo con la telemetria**:
   lo aplazable es la telemetria *fina* (dashboards, alerting calibrado, tracing exhaustivo); la
   **senal minima que hace observable la slice no es aplazable** y va dentro de ella (ver
   "Observabilidad de la slice").
10. **Spike** — si hay incertidumbre tecnica, un spike timeboxed que produce **conocimiento** (no
    codigo a prod) es una slice valida y explicita.

### 3. Hamburger method — motor de composicion (cuando ninguna heuristica dispara)

Cuando la feature es grande pero no tiene indicadores linguisticos de corte y las heuristicas de
arriba no dan un corte obvio, usa el metodo de la hamburguesa (Gojko Adzic): por tu cuenta, y **con la persona** solo si rechazo
la lista corta:

1. Lista las **tareas/capas** del flujo (consultar datos -> procesar -> notificar -> ...).
2. Para **cada capa**, genera 4-5 **opciones graduadas de calidad/esfuerzo**, de la mas cutre que
   aun vale a la mas completa (p.ej. "enviar email": manual -> automatico generico -> personalizado
   -> con unsubscribe -> integracion externa).
3. **Recorta la hamburguesa**: quita los niveles de calidad que el negocio no necesita.
4. **Primer bocado** = el nivel minimo aceptable de **cada** capa. Esa combinacion es la primera
   slice vertical.
5. **Siguientes bocados** = subir calidad de capas manteniendo consistencia entre ellas.

Es la unica tecnica que **genera opciones graduadas por capa** y las hace tangibles. La skill
`hamburger-method` es una profundizacion opcional si quieres facilitarlo mas a fondo; no es
necesaria para aplicar el procedimiento.

### 4. Calibrador de tamano — Elephant Carpaccio

Si una slice no cabe en el budget, **sigue lonchando**: casi todo se puede cortar mas fino de lo que
parece manteniendo la loncha vertical (Kniberg / Cockburn). El listón mental: cada loncha deberia ser
diminuta y seguir siendo entregable end-to-end.

Ejemplo canonico (calculadora de descuentos): entrada = items, precio, estado; salida = total con
descuento e impuesto. Lonchas: (1) leer dos numeros y multiplicar, imprime subtotal; (2) impuesto
fijo hardcodeado; (3) leer estado y elegir tax de una tabla; (4) primer tramo de descuento; (5)
resto de tramos; (6) formato de salida. Cada loncha se commitea, prueba y "entrega" antes de la
siguiente.

**Y hay una senal que se ve antes de estimar una sola linea: un criterio que cuantifica sobre un
conjunto no pide un cambio, pide un barrido.** "Toda fila de todo almacen", "los seis restantes", "los
siete", "cada payload del arbol". Un barrido es su propia slice, y la que lo lleva dentro de otra cosa
es la que se pasa de tamano sin que nadie lo vea venir, porque **el criterio parece normal**: es
falsable, esta bien redactado y cabe en una linea.

Es la senal mas barata que hay, porque opera sobre el texto del criterio y no sobre una estimacion. Y
es la que mas cuesta cuando se salta: medido en una feature real, las dos slices mas caras fueron las
dos que barrian un conjunto -"los seis almacenes restantes" y "toda fila de todo almacen"- y se
llevaron la mitad del presupuesto de las nueve. La segunda agoto su tope de coste **y** sus reintentos
de verificacion sin converger, con tres rechazos del juez por defectos distintos, y hubo que terminarla
a mano. La mas barata de la feature fue la que hacia una cosa sola.

**El corte es partir el barrido de lo que lo habilita**: una slice que introduce la pieza compartida y
la estrena en un solo caso, y otra que la aplica al resto. La primera prueba el diseno con un consumidor
real; la segunda es mecanica y se juzga rapido. Al reves -barrer y disenar a la vez- cada rechazo del
juez llega despues de haber tocado N sitios, y corregirlo los toca todos otra vez.

**Y agotar el presupuesto sin converger es el sintoma, no la senal**: llega cuando ya lo has pagado.

## Observabilidad de la slice

Cortar bien incluye decidir **como se vera vivo** lo que cortas. La regla: toda slice que cambia
comportamiento observable en produccion declara su linea `SENAL:` (como se comprueba viva); las demas
declaran `SENAL: exenta - <motivo>`. Ausencia silenciosa no es exencion.

El detalle -la escalera para decidir si hace falta instrumentar o la senal ya existe, el stack
concreto (libreria de monitoring, repo de alertas, repo de paneles), y como se redacta la linea- vive
en **`observabilidad.md`**: cargalo cuando el corte tenga senal que disenar.

Lo que si es del troceo:

- **Alertas y paneles son slices propias.** Viven en otros repos (⇒ PRs distintas por definicion) y se
  declaran con `REPO:` en su linea de slice.
- **Orden forzoso**: no se puede alertar ni pintar una serie que nadie emite. Primero la slice que
  emite la senal, luego (tras deploy y senal viva) la alerta, y por ultimo el panel. Es el mismo
  razonamiento que "Aislamiento de infra": despliega, observa, y luego el paso siguiente.
- **El panel es el mejor candidato al test de despriorizacion**: si tu set de slices no tiene ninguna
  posponible, el panel casi siempre lo es.

## Validacion del corte

Ademas de validar cada slice contra los criterios, valida el **conjunto**:

- **Prevuelo de sustitucion** — antes de dar cada slice por buena, pregunta si sustituye algo que ya
  esta funcionando, **y hazlo con la pregunta que corresponde al sujeto**. En un servicio desplegado:
  ¿sustituye comportamiento vivo? Si es si, el mecanismo va por **Parallel changes** (ver "Mecanismos de
  slicing seguro"), salvo excepcion de las que ese bullet nombra. En un programa que se instala:
  **¿deja ilegible o inservible algo que ya esta escrito?** -ficheros, filas de un almacen, estado
  persistido, etiquetas- y si es si, **que pasa con lo que ya existe**.

  Es la pregunta que se acaba haciendo cuando la slice ya esta implementada, y entonces cuesta rehacerla;
  hacerla aqui es gratis. **Y hacerla con la forma equivocada es peor que no hacerla**: medido en una
  feature real, la version de servicio aplicada a un programa que se instala no cazo ni una de sus tres
  roturas de formato, y las tres se descubrieron en la maquina de quien lo usaba -una de ellas impidiendo
  cerrar cualquier slice-.
- **Test de despriorizacion** (Lawrence) — un buen set de slices tiene **al menos una que podrias
  tirar o posponer** sin perder el core. Si no puedes despriorizar ninguna, probablemente cortaste
  por trocear (horizontal disfrazado) en vez de por valor. Es el mejor detector de "slices sin
  valor".
- **Cadena de observabilidad completa** — si alguna slice emite una senal nueva relevante, el conjunto
  debe tener su slice de alerta (y de panel si aporta), o una **decision explicita** de no tenerlas. Que
  falten por olvido es como cortar sin criterios de aceptacion: se descubre en el incidente.
- **Igualdad de tamano** — prefiere slices de tamano parecido (cuatro de ~2 mejor que una de 5 + una
  de 3): maximiza la flexibilidad de priorizacion y evita la slice-monstruo escondida.

## Mecanismos de slicing seguro

Como llega una slice vertical a prod siendo reversible y desplegable sola sin romper nada:

- **Expand / migrate / contract** — (1) anade lo nuevo sin retirar lo viejo; (2) activa el nuevo
  camino (flag, dual-write, doble lectura); (3) retira el viejo cuando nadie lo usa.
- **Parallel changes** — para cambios que **sustituyen comportamiento ya en produccion**, es el
  **default**, no una opcion: nuevo adaptador/proveedor/regla detras de flag, viejo activo por
  defecto, y contract cuando el flag este al 100% tras un periodo de observacion. Sustituir in-place
  solo si la ruta no esta expuesta, no hay implementacion previa, o la conmutacion runtime es
  inviable (justificar).
- **Feature flags** — desplegar codigo oculto tras un flag permite mergear slices pequenas de forma
  continua; apagar el flag = rollback instantaneo. El walking skeleton suele vivir tras un flag
  hasta estar listo.
- **Branch by abstraction** — para reemplazos/migraciones grandes sin ramas largas: introduce una
  capa de abstraccion, migra la implementacion por debajo en slices pequenas, retira la vieja al
  final. Complementa expand/contract.
- **Dark launching** — ejecutar el camino nuevo en produccion sin exponerlo al usuario para validar
  con trafico real.
- **Aislamiento de infra y migraciones** — las migraciones de schema y los cambios de infra van en
  **PRs distintas** del codigo aplicativo que las consume: se despliega la migracion, se observa, y
  luego el codigo; permite rollback del codigo sin tocar la BD. Orden tipico para un campo nuevo:
  (1) migracion + columna nullable + modelo; (2) dominio + aplicacion + vistas que lo usan; (3)
  cleanup/backfill/contract.

## Defaults universales

- **Budget de tamano:** **~300-400 lineas de diff por PR** como default recomendado. Es una guia de
  blast radius, no una ley fisica; un repo puede afinarlo. Si una slice lo supera, trocearla.
- **Verificacion post-deploy:** cada slice que llega a prod define **como se comprueba su
  comportamiento vivo** — evidencia observable, ejecutable, con su assert y su via de rollback. Eso
  es exactamente la linea `SENAL:` del contrato de la spec, y quien despliega es quien la comprueba. La
  **forma** depende del repo: un servicio HTTP mirara errores/latencia en el edge; una lib o CLI, una
  invocacion + salida esperada; un job, un efecto observable. No hardcodees el mecanismo HTTP como si
  fuera universal.

## Anti-patterns

- Mezclar migracion de schema con el codigo que la usa en la misma PR.
- Mezclar refactor con feature en la misma PR.
- Sustituir in-place un adaptador/proveedor ya en produccion sin flag ni expand-contract cuando
  existe implementacion previa (rollback solo via redeploy = blast radius innecesario).
- **Cambiar la forma de algo que el programa relee -un fichero, una fila, el estado persistido- sin
  declarar que pasa con lo que ya esta escrito.** El equivalente del anterior para un programa que se
  instala, y se cuela mas facil porque reinstalar parece rollback y no lo es: la version anterior
  tampoco sabe leer lo que escribio la nueva, asi que volver atras mueve el fallo de un conjunto de
  filas al otro en vez de quitarlo.
- **Un criterio que cuantifica sobre un conjunto** ("toda fila de todo almacen", "los seis restantes")
  **dentro de una slice que ademas introduce la pieza**. Son dos slices: la que estrena el diseno en un
  caso real, y la que barre el resto.
- Slices que solo aportan andamiaje y no son desplegables solas.
- Anadir campos, metodos o clases "que necesitaremos en la slice siguiente".
- PRs que dependen de un orden concreto de merge para no romper produccion.
- Nombrar slices por capa tecnica cuando el corte vertical SI cabia en el budget (el horizontal es
  para cuando el vertical no entra, no por defecto).
- Slices que cambian comportamiento en prod **sin senal declarada** (ni exencion escrita): quien
  despliega no sabe que mirar y nadie lo decidio.
- Meter la alerta o el panel **en la misma PR** que la metrica que consumen.
- Dejar el caso mas arriesgado para el final.
- Slices con "y"/"o" en el titulo que esconden varias features.
- Un set de slices donde **no puedes despriorizar ninguna** (senal de corte horizontal disfrazado).
- Dos slices que definen **cada una su mitad** del mismo contrato de frontera: o lo fija una sola
  antes que las dos, o el formato se decide dos veces y alguien reconcilia despues.

## Fuentes

- Bill Wake — *INVEST in Good Stories, and SMART Tasks* (xp123.com, 2003).
- Richard Lawrence / Humanizing Work — *The Guide to Splitting User Stories* y *Story Splitting
  Flowchart* (patrones de corte + test de despriorizacion + igualdad de tamano).
- Gojko Adzic — *Splitting user stories: the hamburger method* (gojko.net, 2012).
- Mike Cohn — *SPIDR: Five Simple but Powerful Ways to Split User Stories* (Mountain Goat).
- Henrik Kniberg — *Elephant Carpaccio facilitation guide* (Crisp, 2013); ejercicio de Alistair
  Cockburn.
- Cockburn; Freeman & Pryce (*GOOS*) — walking skeleton. Hunt & Thomas (*The Pragmatic Programmer*)
  — tracer bullets.
