# Como se escribe una convención

Esta es la vara de las varas, y lo que rige es **la vara del código**: los ficheros de capa de
`docs/conventions/` y cualquier otro `.md` que un contrato mida o que un agente lea como vara. Lo que
obliga a mantener un documento no es la carpeta en la que vive: es que algo se rompa cuando deje de ser
verdad, y lo que se rompe aquí es que un agente que no puede preguntar mida con una foto vieja.

**No rige para los documentos de como se trabaja aquí**, aunque vivan en esta carpeta. Los lee una
persona en sesión, no viajan en el prompt de nadie y su valor es exactamente el que aquí se prohibe:
nombrar el fichero que va a dar conflicto **es** el dato, y decir cuántas veces ya fallo un reparto es
lo único que impide repetirlo. Un documento que nadie usa para bloquear código no necesita seguir siendo
verdad dentro de veinte slices: necesita ser útil hoy, y se corrige el día que engane.

Quedan fuera, por lo mismo, los `.md` del flujo viejo (`skills/`), que son código que no es referencia
(ver `CLAUDE.md`): están congelados a propósito y reescribirlos no compra nada.

Una convención la leen dos agentes que no pueden preguntar -el implementador antes de escribir, el
juez antes de bloquear- y una persona que llega nueva. Los tres necesitan lo mismo: **la regla con la
que se mide el código**, en una forma que siga siendo verdad dentro de veinte slices.

## Un dato del código escrito en prosa: las tres formas

No todas cuestan lo mismo, y la diferencia no es el estilo sino **quien avisa cuando el código cambia**:

| | quien avisa | coste |
|---|---|---|
| **Regla atemporal** | nadie tiene que avisar: sigue siendo verdad | ninguno |
| **Copia medida por un contrato** | `make check`, al instante | se arregla en la misma vuelta |
| **Censo sin contrato** | el juez, dos pasos después | una vuelta entera al implementador |

La segunda **es aceptable** cuando un test compara la copia con su origen -un número de `Budgets`
repetido en prosa, por ejemplo-: cambiar uno sin el otro pone `make check` en rojo antes de que nadie
juzgue nada. Lo que la hace aceptable es que el contrato **compara el dato y no la prosa**,
de modo que reescribir el texto no rompe nada mientras los dos lados digan lo mismo.

Lo que sigue prohibe la tercera. Si un dato del código tiene que estar escrito, **se le pone contrato o
no se escribe**.

## Reglas críticas

- **Una convención no cuenta cuántos hay.** Ni "los tres reintentos", ni "las nueve etiquetas", ni
  "el único código que emiten los dos subcomandos". Un conteo es una foto del código, y la próxima
  slice que añada un miembro la convierte en mentira.
- **Ni enumera en lista cerrada.** "Lo que acumula por invocación son estos tres" caduca igual que un
  número, y una enumeración **al lado de una tabla que si tiene contrato** caduca igual que si estuviera
  sola: lo que protege es el contrato, no la vecindad. Si la lista importa, vive en el código, que es
  donde se puede comprobar.
- **Ni narra la historia.** Que algo vivio antes en otro sitio, que se descarto una alternativa o que
  un fallo costó un run es el **por que**, y su casa es el cuerpo de la pull request. La convención dice la
  regla; el registro duradero dice como se llegó a ella.
- **Ni señala ficheros reales como ancla normativa.** "Es el caso de este adaptador concreto" obliga
  a mantener la prosa cada vez que ese fichero se mueve. Si la regla necesita ancla, se da como
  **molde**. Lo que si se nombra es **la herramienta que mide** -el test que compara las dos copias de
  un contrato, el linter que caza la firma larga-: eso no es un ejemplo de como se hace, es donde falla
  si no se hace.
- **Cada fichero cubre una capa, y un tema que se quiera cargar solo se saca a fichero propio.** No por
  tamano: un documento largo y enfocado se cumple igual que uno corto -está medido-. Es por **poder cargar solo lo que toca**: mientras un tema viva dentro de
  otro, quien solo necesita ese tema se lleva los dos.

## El molde, cuando hace falta

Un molde es código de ejemplo con rutas y nombres **plantilla**, que no apuntan a nada del árbol:

```python
# ejemplo/infrastructure/{cosa}.py  -- puerto y adaptador juntos
class {Cosa}(ABC):
    @abstractmethod
    def hacer(self) -> None: ...


class Local{Cosa}({Cosa}):
    def hacer(self) -> None: ...
```

- **La ruta del molde no empieza por una carpeta de este repo.** Si empezara por una, el contrato de
  rutas citadas (`test_pipeline_invariants.py`) la leeria como una afirmación sobre el árbol y
  fallaria, con razón: en backticks, una ruta de este repo es una promesa de que existe.
- **El molde no mejora el acierto: ahorra el trabajo de averiguarlo.** Sin el se acierta igual, pero se
  gastan turnos yendo a mirar el árbol para confirmar. Por eso el molde se pone donde el caso es
  frecuente, no en todas las reglas.

## Antipatrones

- Un número escrito en prosa que cuente miembros, ramas, contadores o ficheros.
- Una lista cerrada de lo que hay hoy, presentada como si fuese la regla.
- Un párrafo que cuenta lo que se intento antes. **Va al cuerpo de la pull request.**
- Una ruta de este repo usada como ejemplo de "así se hace" en vez de un molde plantilla.
- Una regla que obliga al implementador a editar `docs/conventions/` para dejarla veraz: si mantener
  la convención es parte de cada slice, la convención ha dejado de ser vara y es un fichero de código
  más. Quien escribe no puede ser quien mueve la vara con la que se le mide.
