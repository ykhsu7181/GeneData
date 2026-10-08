#!/usr/bin/env bash
set -euo pipefail

# Build a versioned, immutable JBrowse Web directory for later Nginx deployment.
# This script does not edit Nginx configuration or switch a production symlink.

readonly JBROWSE_VERSION="4.3.0"
readonly JBROWSE_ARCHIVE="jbrowse-web-v${JBROWSE_VERSION}.zip"
readonly JBROWSE_URL="https://github.com/GMOD/jbrowse-components/releases/download/v${JBROWSE_VERSION}/${JBROWSE_ARCHIVE}"
readonly JBROWSE_SHA256="a9d42417102ee088a1cbf85c6d857c1065d66984ea6c56f3115ef9dd56d76702"

usage() {
    printf 'Usage: %s OUTPUT_DIRECTORY\n' "$0" >&2
    printf 'Example: %s /home/labuser/rdcheng/gd/releases/jbrowse2-v%s\n' "$0" "$JBROWSE_VERSION" >&2
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

for command_name in curl sha256sum unzip mktemp; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required command is missing: %s\n' "$command_name" >&2
        exit 1
    fi
done

output_directory="${1%/}"
if [[ -z "$output_directory" || "$output_directory" != /* ]]; then
    printf 'OUTPUT_DIRECTORY must be an absolute path.\n' >&2
    exit 2
fi

if [[ -e "$output_directory" ]]; then
    printf 'Refusing to overwrite existing path: %s\n' "$output_directory" >&2
    exit 1
fi

parent_directory="$(dirname "$output_directory")"
mkdir -p "$parent_directory"
temporary_directory="$(mktemp -d "${parent_directory}/.jbrowse2-v${JBROWSE_VERSION}.XXXXXX")"
archive_path="${temporary_directory}/${JBROWSE_ARCHIVE}"
unpack_directory="${temporary_directory}/unpacked"

cleanup() {
    if [[ -d "$temporary_directory" ]]; then
        rm -rf -- "$temporary_directory"
    fi
}
trap cleanup EXIT

printf 'Downloading JBrowse Web v%s...\n' "$JBROWSE_VERSION"
curl --fail --location --retry 3 --retry-delay 2 --output "$archive_path" "$JBROWSE_URL"
printf '%s  %s\n' "$JBROWSE_SHA256" "$archive_path" | sha256sum --check --status

mkdir "$unpack_directory"
unzip -q "$archive_path" -d "$unpack_directory"

if [[ ! -f "$unpack_directory/index.html" ]]; then
    printf 'Downloaded package does not contain index.html.\n' >&2
    exit 1
fi

if [[ "$(tr -d '\r\n' < "$unpack_directory/version.txt")" != "$JBROWSE_VERSION" ]]; then
    printf 'Downloaded package version.txt does not match %s.\n' "$JBROWSE_VERSION" >&2
    exit 1
fi

if ! grep -q 'src="static/' "$unpack_directory/index.html"; then
    printf 'JBrowse entry point does not use the expected relative static asset path.\n' >&2
    exit 1
fi

mv -- "$unpack_directory" "$output_directory"
printf 'JBrowse Web v%s is ready at %s\n' "$JBROWSE_VERSION" "$output_directory"
printf 'Archive SHA-256: %s\n' "$JBROWSE_SHA256"
