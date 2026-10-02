#!/bin/sh
# Build the release archives of the icon themes.
#
# The archive has the theme directory at the top level and keeps the symlinks,
# which is what store.kde.org and a plain extraction into ~/.local/share/icons
# expect. The name is <Theme>-<version>.<format>, with the version read from the
# VERSIONS file in the root of the repo.
#
# Usage: tools/package.sh [-f tar.gz|zip|both] [-o DIRECTORY] [THEME ...]
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
versions="$root/VERSIONS"
outdir="$root/dist"
format=tar.gz
themes=""

usage() {
    # the header block, up to the first line that is not a comment
    sed -n '2,${/^#/!q; s/^# \{0,1\}//; p;}' "$0"
}

theme_version() {
    awk -F= -v name="$1" '
        /^[[:space:]]*#/ { next }
        NF < 2 { next }
        { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
          if ($1 == name) { print $2; exit } }
    ' "$versions"
}

all_themes() {
    awk -F= '
        /^[[:space:]]*#/ { next }
        NF < 2 { next }
        { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1); print $1 }
    ' "$versions"
}

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--format) format=$2; shift 2 ;;
        -o|--outdir) outdir=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
        *) themes="$themes $1"; shift ;;
    esac
done

case "$format" in
    tar.gz|zip|both) ;;
    *) echo "invalid format: $format (tar.gz, zip, both)" >&2; exit 2 ;;
esac

[ -f "$versions" ] || { echo "missing $versions" >&2; exit 1; }
[ -n "$themes" ] || themes=$(all_themes)

mkdir -p "$outdir"
# absolute, since the zip is written from inside src/
outdir=$(cd "$outdir" && pwd)
status=0

for name in $themes; do
    dir="$root/src/$name"
    version=$(theme_version "$name")

    if [ -z "$version" ]; then
        echo "$name: no version in VERSIONS, skipped" >&2
        status=1
        continue
    fi
    if [ ! -d "$dir" ]; then
        echo "$name: missing $dir, skipped" >&2
        status=1
        continue
    fi
    if [ ! -f "$dir/index.theme" ]; then
        echo "$name: missing index.theme, skipped" >&2
        status=1
        continue
    fi

    declared=$(sed -n 's/^Name=//p' "$dir/index.theme" | head -1)
    [ "$declared" = "$name" ] || \
        echo "$name: warning, index.theme declares Name=$declared" >&2
    stamped=$(sed -n 's/^Version=//p' "$dir/index.theme" | head -1)
    if [ -z "$stamped" ]; then
        echo "$name: warning, index.theme has no Version key" >&2
    elif [ "$stamped" != "$version" ]; then
        echo "$name: index.theme says Version=$stamped instead of $version, skipped" >&2
        status=1
        continue
    fi

    if [ "$format" = tar.gz ] || [ "$format" = both ]; then
        out="$outdir/$name-$version.tar.gz"
        rm -f "$out"
        tar -C "$root/src" --sort=name --owner=0 --group=0 --numeric-owner \
            --exclude-vcs -czf "$out" "$name"
        echo "$out ($(du -h "$out" | cut -f1))"
    fi

    if [ "$format" = zip ] || [ "$format" = both ]; then
        out="$outdir/$name-$version.zip"
        rm -f "$out"
        # -y stores the symlinks instead of duplicating their content
        (cd "$root/src" && zip -q -r -y "$out" "$name")
        echo "$out ($(du -h "$out" | cut -f1))"
    fi
done

exit $status
