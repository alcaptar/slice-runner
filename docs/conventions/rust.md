# Rust

Rige para todo `.rs` de `tui/`. **No es una vara aparte**: `code-style.md`, `architecture.md`,
`domain.md`, `application.md`, `infrastructure.md` y `testing.md` valen igual para el código Rust, y
este fichero solo dice **como se escribe cada regla en Rust** y declara, con su motivo, donde el lenguaje
obliga a desviarse. Una regla que no aparezca aquí se aplica tal como la escriben esos ficheros.

Lo que miden el compilador y `clippy` falla en `make tui-lint`. Lo que ninguno de los dos ve -los
comentarios, las rutas relativas en los `use`, una dependencia externa en `domain/` y un proceso lanzado
que nadie puede matar- lo mide `tests/test_tui_invariants.py` dentro de `make check`.

## Traducción de las reglas

| Regla | En Rust |
|---|---|
| Cero prosa | Ni `//`, ni `///`, ni `//!`. |
| Ninguna función suelta | Toda función es método o función asociada de un `impl` de un `struct`, un `enum` o un `trait`. |
| Sin imports relativos | `use crate::...`, nunca `super::` ni `self::`. Un `use` al principio del fichero, agrupados: `std`, terceros, `crate`. |
| Formato | `rustfmt`, con el ancho de línea de `tui/rustfmt.toml`. |
| Value object | `struct` sin campos `pub`, construido por una función asociada que valida, con `#[derive(Debug, Clone, PartialEq)]`, y `Eq` cuando todos sus campos lo admiten: un `f64` no. |
| Vocabulario cerrado | `enum`. Todo `match` sobre él es exhaustivo y sin `_`: lo mide `wildcard_enum_match_arm`. |
| Puerto | `trait`. Vive en `domain/` salvo que solo lo consuma la infraestructura, como en Python. |
| Excepciones del dominio | Un `enum` de error en el `errors.rs` de `domain/`, devuelto en un `Result`. |
| Pydantic en la frontera | `serde` solo en `infrastructure/`. El modelo de frontera convierte al dominio en su propio `impl`, y un error de `serde` se traduce al error del dominio sin salir de la capa. |
| Contrato completo | `#[serde(deny_unknown_fields)]`. |
| Proyección de un formato abierto | Un `struct` con solo las claves que se consumen, sin `deny_unknown_fields`: lo desconocido se ignora y lo declarado que llega mal rompe. |
| `create_autospec` | Un doble a mano que implementa el `trait` y registra lo que recibe. |
| Doble inyección | El adaptador recibe por constructor un `trait` propio y estrecho sobre lo externo -lanzar un hijo, abrir un pseudoterminal-, no el de la librería entera, y su test le pasa un doble a mano. Su implementación real es el paso directo, y es lo único que nombra `Command::new`, `CommandBuilder::new` o el sistema de pseudoterminales. |

## Lo que solo existe en Rust

- **Nada de `unwrap()`, `expect()` ni `panic!` en producción.** Un fallo se devuelve como `Result` y lo
  decide quien sabe que hacer con el. Lo miden los lints de `tui/Cargo.toml`, y `tui/clippy.toml` los
  permite en tests, donde un pánico **es** el fallo del test.
- **Nada de `unsafe`.** `unsafe_code = "forbid"` en `tui/Cargo.toml`.
- **El dominio no depende de `ratatui`, `crossterm`, `serde`, `portable_pty`, `vt100` ni `tui_term`.** Es la traducción de que `domain/` no
  conoce a nadie: en Rust las dependencias se ven en el `use`, y un `use ratatui` en `domain/` es el
  mismo fallo que un import de infraestructura en Python.

## Procesos externos

El tope por llamada de `infrastructure.md` se aplica igual, y `std::process::Command` no lo trae: el
adaptador recibe el presupuesto como `Duration` por constructor, sin `Default`, espera con plazo y al
agotarlo **mata al hijo y descarta lo que hubiera escrito**. El plazo lo mide el `Clock` que recibe, no
`Instant::now()`, para que su test lo agote con un reloj doble y sin dormir.

**Un proceso sin tope por diseño** es la única excepción, y hay dos, cada una con su motivo: un flujo que
se sigue mientras la interfaz esta abierta, y una sesión interactiva de `claude` en un pseudoterminal que
vive mientras la interfaz esta abierta. Se lanza desde un adaptador que lo dice en su nombre, y el hijo
muere cuando el adaptador se suelta, en su `impl Drop`, también si la interfaz cae por un pánico. El
lanzamiento con `CommandBuilder::new` exige `.kill()` en el mismo fichero igual que `Command::new`. Lo que
no vale es un proceso sin tope lanzado desde cualquier otro sitio.

## Paleta

**La interfaz solo usa colores con nombre**: `Color::Red`, `Color::DarkGray` y el resto de los
del terminal, más `Color::Reset` para el texto y el fondo por omisión. Nunca `Color::Rgb` ni
`Color::Indexed`. Así la paleta es un vocabulario cerrado que no crece con cada pantalla, y un color
nuevo es una decisión de diseño que se ve en el diff, no un hexadecimal suelto.

Cada nombre tiene un valor fijo, que es el que usa toda maqueta de la interfaz y el que pinta una captura.
El terminal de quien la usa puede pintar otro tono según su tema: la tabla fija con que se compara, no lo
que se ve en cada máquina. El conversor de capturas la lee de este fichero, así que no tiene copia.

| Color | Valor |
|---|---|
| `Reset` (texto) | `#d8dde6` |
| `Reset` (fondo) | `#0f1216` |
| `Black` | `#14171c` |
| `Red` | `#ef6b6b` |
| `Green` | `#6fcf8a` |
| `Yellow` | `#f2b53b` |
| `Blue` | `#6b9cf2` |
| `Magenta` | `#c58af2` |
| `Cyan` | `#5cc8e0` |
| `Gray` | `#8a93a3` |
| `DarkGray` | `#6b7280` |
| `LightRed` | `#f59a9a` |
| `LightGreen` | `#9fe0b0` |
| `LightYellow` | `#f7cf7a` |
| `LightBlue` | `#9dbdf7` |
| `LightMagenta` | `#dab3f7` |
| `LightCyan` | `#93dcec` |
| `White` | `#f4f6f9` |

## Estructura

```
ejemplo/
  Cargo.toml
  src/
    main.rs               solo delega en el entrypoint de infrastructure
    domain/
    application/
    infrastructure/
    tests/                co-localizados bajo #[cfg(test)], espejando las capas
      mothers/
      doubles.rs
```

Los ejemplos de un contrato que el programa de Python emite **no se copian** a `tui/`: los tests los
leen de `contract/` en disco, desde `env!("CARGO_MANIFEST_DIR")`, para que un cambio de un lado rompa el
otro.

## Desviaciones declaradas

- **`fn main` es una función suelta**, porque Rust la exige así. No hace nada más que delegar.
- **Un test es una `fn` con `#[test]` dentro de un `mod`**, porque el arnés de Rust no ejecuta métodos.
  El `mod` hace el papel de la clase de test: agrupa por el comportamiento que fija, y su nombre y el de
  la función forman la frase. Los helpers son funciones asociadas de un `struct` del módulo de test, no
  `fn` sueltas.
- **Dobles a mano en vez de `create_autospec`**, porque Rust no tiene un equivalente sin una
  dependencia de macros que genere código que nadie lee. El `trait` ya garantiza lo que `spec_set` daba
  en Python: un doble que no lo cumple no compila.

## Antipatrones

- Un `unwrap()`, `expect()` o `panic!` fuera de un test.
- Un `_` en un `match` sobre un `enum`.
- `serde`, `ratatui`, `crossterm`, `portable_pty`, `vt100` o `tui_term` en `domain/`.
- Un `Command` o `CommandBuilder` lanzado sin tope fuera de un adaptador que declara un proceso sin tope.
- Un ejemplo de contrato copiado dentro de `tui/` en vez de leído de `contract/`.
- Un comentario o un doc comment.
- Un `Color::Rgb` o un `Color::Indexed`: el color que no está en la paleta.
