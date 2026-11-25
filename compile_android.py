"""Compile l'APK de test avec le buildozer.spec du projet, puis vérifie ses bibliothèques ARM64."""
import io
import os
import tarfile
from pathlib import Path
import struct
import subprocess
import sys
from zipfile import ZIP_STORED, ZipFile

PROJECT = Path(__file__).resolve().parent
PAGE = 16384


def verify_elf(data, name):
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError(f"Bibliothèque ELF ARM64 invalide : {name}")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    loads = 0
    for index in range(count):
        kind, _, offset, address, _, _, _, align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * size)
        if kind == 1:
            loads += 1
            if align < PAGE or (address - offset) % PAGE:
                raise ValueError(f"Segment ELF incompatible avec 16 Ko : {name}")
    if not loads:
        raise ValueError(f"Aucun segment chargeable : {name}")


def verify_apk(path):
    """Contrôle les segments ELF PT_LOAD et les offsets ZIP des bibliothèques non compressées."""
    checked = 0
    with ZipFile(path) as archive, path.open("rb") as raw:
        libs = [entry for entry in archive.infolist()
                if entry.filename.startswith("lib/arm64-v8a/") and entry.filename.endswith(".so")]
        if not libs:
            raise ValueError("Aucune bibliothèque native ARM64 dans l’APK.")
        for lib in libs:
            data = archive.read(lib)
            if lib.filename.endswith("/libpybundle.so") and not data.startswith(b"\x7fELF"):
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as bundle:
                    for member in bundle:
                        if member.isfile() and member.name.endswith(".so"):
                            verify_elf(bundle.extractfile(member).read(), member.name)
                            checked += 1
            else:
                verify_elf(data, lib.filename)
                checked += 1
            if lib.compress_type == ZIP_STORED:
                raw.seek(lib.header_offset + 26)
                name_size, extra_size = struct.unpack("<HH", raw.read(4))
                if (lib.header_offset + 30 + name_size + extra_size) % PAGE:
                    raise ValueError(f"Alignement ZIP incompatible avec 16 Ko : {lib.filename}")
    if not checked:
        raise ValueError("Aucune bibliothèque ELF contrôlée.")
    return checked


def build():
    if not (PROJECT / "buildozer.spec").is_file():
        raise FileNotFoundError("buildozer.spec est requis dans le dossier du projet.")
    # Use an existing Buildozer when available. Bootstrap missing tools inside WSL.
    command = """
set -eu
export PATH="$HOME/.local/bin:$PATH"
if ! command -v buildozer >/dev/null; then
    envdir="$HOME/.local/share/gestion-budget/build-env"
    if [ ! -x "$envdir/bin/buildozer" ]; then
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-dev build-essential git zip unzip openjdk-17-jdk autoconf automake libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev
        python3 -m venv "$envdir"
        "$envdir/bin/python" -m pip install buildozer setuptools 'cython<3'
    fi
    export PATH="$envdir/bin:$PATH"
fi
exec buildozer android debug
"""
    if os.name == "nt":
        subprocess.run(["wsl", "--cd", str(PROJECT), "bash", "-lc", command], check=True)
    else:
        subprocess.run(["buildozer", "android", "debug"], cwd=PROJECT, check=True)


def main():
    folder = PROJECT / "bin"
    before = {path: path.stat().st_mtime_ns for path in folder.glob("*.apk")}
    build()
    produced = [path for path in folder.glob("*.apk") if path.stat().st_mtime_ns != before.get(path)]
    if len(produced) != 1:
        raise RuntimeError("Impossible d’identifier un unique APK produit par cette compilation.")
    path = produced[0]
    count = verify_apk(path)
    print(f"APK de test : {path}\n{count} bibliothèques ARM64 contrôlées pour les pages de 16 Ko.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
