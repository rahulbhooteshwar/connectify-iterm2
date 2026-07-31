#!/bin/bash
set -e

# Connectify installer - bootstrap only.
#
# This does the little that has to happen before Connectify exists on the
# machine: work out the architecture, fetch the release archive and unpack it.
# Everything after that - requirement checks, installing, iTerm2 profiles, PATH
# guidance - is done by the build we just downloaded, which brings its own UI
# along and so needs nothing installed on the host.

VERSION="${CONNECTIFY_VERSION:-latest}"
GITHUB_REPO="rahulbhooteshwar/connectify-iterm2"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/connectify-install-XXXXXX")"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

say() { printf "${CYAN}›${NC} %s\n" "$1"; }
ok()  { printf "  ${GREEN}✔${NC} %s\n" "$1"; }
die() { printf "  ${RED}✘${NC} %s\n" "$1"; exit 1; }

banner() {
    printf "\n${CYAN}╭────────────────────────────────────────────────────────────╮${NC}\n"
    printf "${CYAN}│${NC}  ${BOLD}Connectify${NC}  ${DIM}SSH Session Manager for iTerm2${NC}                ${CYAN}│${NC}\n"
    printf "${CYAN}╰────────────────────────────────────────────────────────────╯${NC}\n\n"
}

check_macos() {
    [[ "$OSTYPE" == darwin* ]] || die "Connectify only runs on macOS"
}

detect_architecture() {
    # Releases ship one build per architecture. On Apple Silicon a shell running
    # under Rosetta reports x86_64, which is still the right build for it.
    case "$(uname -m)" in
        arm64)  echo "arm64" ;;
        x86_64) echo "amd64" ;;
        *)      die "Unsupported architecture: $(uname -m)" ;;
    esac
}

resolve_version() {
    # Ask GitHub which release is current, so the version can be shown up front
    if [[ "$VERSION" != "latest" ]]; then
        echo "${VERSION#v}"
        return
    fi

    local tag
    tag=$(curl -fsSL "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" 2>/dev/null \
          | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
    echo "${tag#v}"
}

download() {
    local version="$1" arch="$2"
    local archive="connectify-macos-${arch}.tar.gz"
    local url="https://github.com/${GITHUB_REPO}/releases/download/v${version}/${archive}"

    say "$(printf "Downloading Connectify ${BOLD}v%s${NC} ${DIM}(%s)${NC}" "$version" "$arch")" >&2

    if ! curl -fL --progress-bar "$url" -o "${TEMP_DIR}/${archive}" >&2; then
        printf "\n" >&2
        die "Could not download ${archive} from ${url}"
    fi

    ok "$(du -h "${TEMP_DIR}/${archive}" | cut -f1 | tr -d ' ') downloaded" >&2
    echo "${TEMP_DIR}/${archive}"
}

main() {
    banner
    check_macos

    local arch version archive
    arch=$(detect_architecture)

    say "Looking up the latest release"
    version=$(resolve_version)
    [[ -n "$version" ]] || die "Could not work out which version to install. Set CONNECTIFY_VERSION=x.y.z to pick one."
    ok "v${version}"

    archive=$(download "$version" "$arch")

    say "Unpacking"
    tar -xzf "$archive" -C "$TEMP_DIR"
    [[ -x "${TEMP_DIR}/connectify/connectify" ]] || die "The archive did not contain a Connectify build"
    ok "Ready"

    # Hand over to the build's own installer: it does the checks, the copying,
    # the iTerm2 profiles and the instructions, with a proper UI
    "${TEMP_DIR}/connectify/connectify" install \
        --from "${TEMP_DIR}/connectify" --version "$version"
}

main
