# Estilo de código

Rige para **todo `.py` nuevo**. Los scripts viejos de `skills/` no la cumplen todavía: ver la lista
de lo que no es referencia en `CLAUDE.md`.

## Reglas críticas

- **Cero prosa: ni comentarios ni docstrings.** Nada de `#`, y tampoco docstring de módulo, de
  clase, de función ni de atributo. La única excepción es el shebang.
- **Ninguna función suelta a nivel de módulo: toda función cuelga de una clase.** Metodo,
  `@classmethod` o `@staticmethod`, incluido el `main` de un ejecutable. La única excepción la declara
  `docs/conventions/testing.md`, y es un fixture cuyo alcance **es** el módulo entero.
- **El código va en ingles.** Nombres de fichero y de módulo, clases, funciones, metodos, variables,
  parametros, constantes, miembros de enum, excepciones, nombres de test, nombres de subcomando, y
  los mensajes de error que ve una persona.
- **Sin imports relativos.** Lo mide `TID` en `ruff`.

## Por que cero prosa

Si un trozo de código no se entiende sin un párrafo al lado, **el arreglo es el código y no el
párrafo**: nombres que digan lo que hacen, funciones pequeñas con una responsabilidad, tipos que
hagan imposible el mal uso, constantes con nombre en vez de literales. Un `if` que necesitaba tres
líneas de explicación es casi siempre una función con nombre esperando a nacer, y un invariante que
se explicaba en prosa es casi siempre un test que falta.

El *por que* va al **registro duradero**: el cuerpo de la pull request y `docs/`. Es lo que se sigue
leyendo cuando el fichero ya se ha reescrito tres veces.

## Por que ninguna función suelta

Lo que era una función privada de módulo más un punado de constantes sueltas es casi siempre una
clase esperando a nacer, y ponerle nombre es lo que dice **de quien** es esa lógica.

No es cosmetica: un punado de funciones sueltas que en realidad eran una sola pieza escondio durante un
tiempo que a esa pieza le faltaba un argumento sin el que no hacía su trabajo. Con nombre, la ausencia se
ve.

## Imports

- `from __future__ import annotations` primero, antes de cualquier otro import.
- Siempre al inicio del fichero, **nunca** dentro de funciones, metodos o clases.
- Agrupados: (1) stdlib, (2) terceros, (3) módulos del proyecto. Separados por línea en blanco. Lo
  ordena `I` (isort) en `ruff`, y `known-first-party` declara el paquete del proyecto para que no se
  mezcle con las dependencias de terceros.
- Los imports usados solo en anotaciones van en un bloque `if TYPE_CHECKING:` al final del bloque,
  con el mismo orden interno. El bloque solo se introduce si hay imports que sean solo-tipos.

## Formato

- Línea en blanco antes del `return` y entre bloques logicos de un metodo.
- `line-length = 120`, comillas dobles, formateado por `ruff format`.

## Antipatrones

- Un comentario o un docstring explicando código que se podría renombrar. **Hay que reescribir el
  código.**
- Una función a nivel de módulo. **Hay que buscarle la clase.**
- Un import dentro de una función o de un metodo.
- Un bloque `if TYPE_CHECKING:` vacío, o con imports que se usan en runtime.
- Un identificador en castellano que no sea dato de un contrato.
