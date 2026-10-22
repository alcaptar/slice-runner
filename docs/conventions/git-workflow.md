# Rama, pull request, merge

Esto es para el trabajo **sobre este repo**. Las ramas de una slice (`slice/NN-name`) las gestiona
`slice-runner`, que ya trabajaba así.

## Nada se commitea directamente en `master`

Ni siquiera un typo: hay un hook que bloquea el push sobre la rama protegida, así que descubrirlo tarde
cuesta rehacer el trabajo de sacarlo de `master`.

```bash
git switch -c <type>/<slug>          # refactor/contexto-del-orquestador, docs/flujo-rama-pr-merge
git push -u origin <type>/<slug>
gh pr create                          # cuerpo con la intencion: que estaba mal y deja de estarlo
gh pr merge <N> --merge --delete-branch
git switch master && git pull --ff-only
```

## Las reglas y su motivo

- **`--merge`, no `--squash` ni `--rebase`**: los dos últimos reescriben los hashes y dejan tu `master`
  local divergido de `origin/master`, con lo que el `git pull --ff-only` de después falla y hay que
  resolverlo a mano justo cuando crees que has terminado.
- **El cuerpo de la pull request cuenta el porqué**, no el diff -misma vara que las pull requests que
  abre `slice-runner`: si borras el cambio, ¿que queda roto o imposible?-. Es el registro duradero de
  las decisiones, porque el código no lleva prosa.
- **`make check` en verde antes de abrir la pull request.** `.github/workflows/check.yml` lo corre
  también en **toda** pull request, sin filtro de `paths`, así que la vara se mide donde se decide
  mergear; el local es para no descubrirlo en la integración continua.
- **`git add` con rutas explicitas, nunca `-A` ni `.`** Lo que evita es arrastrar al commit lo que nadie
  declaró; para lo que **no** sirve es para stagear borrados, y la diferencia está medida: `git add --`
  con la ruta de un fichero borrado del árbol **si** lo stagea, pero con la de uno que tampoco está en el
  índice -tras un `git rm`- **aborta entero**, y con `-A` también. Abortado el `add`, el índice se queda
  con una ronda de retraso mientras la higiene, los controles y el bundle siguen saliendo verdes sobre el
  índice viejo. **Para borrar, saca el fichero del árbol y deja que el `add` lo recoja**; antes de dar un
  commit por hecho, `git diff --name-only` tiene que salir vacío.
- **La integración continua se comprueba contra el SHA que vas a mergear**, no contra "la rama": un
  `success` heredado del commit anterior se lee igual en la interfaz.
- **Una pull request lleva los commits que hagan falta, y cada ronda de corrección va en el suyo.**
  Fundir la corrección con lo corregido obliga a quien revisa a reconstruir del diff final que se pidió
  cambiar, y deja el historial sin el orden en que se hizo el trabajo, que es lo único que puede
  acreditarlo. Lo que no cambia por llevar varios: cada commit stagea solo lo declarado, y su mensaje
  sigue siendo convencional con el `name` de la slice como scope.

## Dos slices en paralelo

Dos slices se conducen a la vez en **worktrees distintos**, cada una en su rama. Lo que decide si pueden
ir juntas no es el enunciado de la slice sino **los ficheros que acaba tocando**, y eso no se sabe hasta
implementarla.

- **No estimes el territorio por el nombre de la slice.** Se ha fallado dos veces haciendolo: una pareja
  elegida como "la más disjunta" mirando su fichero protagonista compartio cuatro ficheros, y otra
  compartio siete, incluido uno que **las dos crearon**.
- **Hay ficheros iman que toca casi cualquier slice**: `infrastructure/cli.py` -ahi se monta el grafo de
  dependencias entero-, `src/slice_runner/tests/doubles.py`, `domain/exceptions.py`, `infrastructure/subcommand.py`, el
  `README.md` y `docs/conventions/`. Compartir uno de esos no impide lanzar, pero garantiza una fusión.
- **`application/actions/conduct_slice.py` es el cuello de botella del programa.** Dos slices que lo
  toquen no van juntas: ahi el conflicto deja de ser cosmetico.
- **Al lanzar en paralelo, declara el riesgo en vez de prometer que no lo hay**: "comparten `cli.py`, si
  hay conflicto sera pequeño" es honesto; "son disjuntas" ha resultado falso más veces de las que ha
  resultado cierto.
- **La segunda en mergear fusiona `master` en su rama, y eso no obliga a volver a juzgar.** Una fusión
  no es código nuevo: se resuelve el conflicto, se pasan los controles y se sube. Volver a pagar al juez
  por una resolución de conflicto es gastar la garantía donde no aporta.

## Antipatrones

- Un commit en `master`.
- Dar dos slices por disjuntas sin haber mirado que ficheros toca cada una.
- `--squash` o `--rebase` al mergear.
- Un cuerpo de pull request que resume el diff.
- Fundir una ronda de corrección con el commit que corrige.
- `git add -A`, o dar por bueno un commit sin comprobar que el índice iguala el árbol.
- Leer la integración continua sin comprobar a que SHA corresponde.
