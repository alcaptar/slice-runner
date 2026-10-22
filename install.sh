#!/bin/sh
set -eu

REPOSITORY="alcaptar/slice-runner"

fail() {
    echo "$1" >&2
    exit 1
}

command -v uv >/dev/null 2>&1 || fail "uv no esta instalado: instalalo desde https://docs.astral.sh/uv/ y vuelve a lanzar este script."
command -v gh >/dev/null 2>&1 || fail "gh no esta instalado: instalalo desde https://cli.github.com y vuelve a lanzar este script."
gh auth status >/dev/null 2>&1 || fail "gh no tiene sesion iniciada: ejecuta 'gh auth login' y vuelve a lanzar este script."

tool_bin="$(uv tool dir --bin)"
slice_runner="$tool_bin/slice-runner"
latest="$(gh release view --repo "$REPOSITORY" --json tagName --jq .tagName)"
installed="$(uv tool list 2>/dev/null | awk '$1 == "slice-runner" { print $2 }')"

if [ ! -x "$slice_runner" ] || [ "$installed" != "$latest" ]; then
    download_dir="$(mktemp -d)"
    trap 'rm -rf "$download_dir"' EXIT
    gh release download "$latest" --repo "$REPOSITORY" --pattern 'slice_runner-*-py3-none-any.whl' --dir "$download_dir"
    uv tool install --force "$download_dir"/slice_runner-*-py3-none-any.whl
fi

"$slice_runner" update

case ":$PATH:" in
*":$tool_bin:"*) ;;
*)
    echo "$tool_bin no esta en el PATH, asi que 'slice-runner' no se encontrara por su nombre." >&2
    echo "Anadelo al perfil de tu shell con: export PATH=\"$tool_bin:\$PATH\"" >&2
    ;;
esac
