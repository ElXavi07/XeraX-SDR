"""Prepare verified private source copies; never encode or invoke a native tool."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

PRIMARY_MANIFEST_SHA256 = "e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1"
SUPPORT_SHA256 = "f044b8e7410d23bb4a39ebd79bf20404867b250ce8ae70a2fb57274496723038"
PIN = "590c531391dfd3146073afbc3956f70d42c62a46"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in (".", "..") for p in path.parts):
        raise ValueError("unsafe manifest path")
    if "\\" in value or ":" in value or str(path) != value:
        raise ValueError("noncanonical manifest path")
    return value


def read_originals(root: Path) -> tuple[dict[str, bytes], dict]:
    manifest_bytes = (root / "manifest.json").read_bytes()
    if sha(manifest_bytes) != PRIMARY_MANIFEST_SHA256:
        raise ValueError("primary manifest does not match registered exact bytes")
    manifest = json.loads(manifest_bytes)
    if len(manifest["files"]) != 36 or len(manifest["api_metadata"]) != 6:
        raise ValueError("unexpected primary closure cardinality")
    files = {"manifest.json": manifest_bytes}
    for entry in manifest["files"] + manifest["api_metadata"] + [manifest["source_asset_slice"]]:
        relative = checked_relative(entry["path"])
        if relative in files:
            raise ValueError("duplicate primary path")
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("primary file escapes declared root")
        data = path.read_bytes()
        if len(data) != entry["bytes"] or sha(data) != entry["sha256"]:
            raise ValueError(f"primary identity mismatch: {relative}")
        if "git_blob_sha1" in entry:
            blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
            if hashlib.sha1(blob).hexdigest() != entry["git_blob_sha1"]:
                raise ValueError(f"primary Git blob mismatch: {relative}")
        files[relative] = data
    slice_info = manifest["source_asset_slice"]
    first, last = slice_info["source_interval"]
    if files[slice_info["path"]] != files[slice_info["source"]][first:last]:
        raise ValueError("retained announcement slice differs from original source interval")
    return files, manifest


def patch_encode(original: bytes, classname: str, next_method: str,
                 edits: list[tuple[bytes, bytes]]) -> tuple[bytes, bytes]:
    start_marker = f"void {classname}::encode(".encode("ascii")
    if original.count(start_marker) != 1:
        raise ValueError("encoding method start is ambiguous")
    start = original.index(start_marker)
    end_marker = f"{classname}::{next_method}(".encode("ascii")
    if original.count(end_marker) != 1:
        raise ValueError("encoding method end is ambiguous")
    end = original.index(end_marker, start)
    section = original[start:end]
    for before, after in edits:
        if section.count(before) != 1:
            raise ValueError(f"registered replacement count is not one: {before!r}")
        section = section.replace(before, after, 1)
    patched = original[:start] + section + original[end:]
    diff = "\n".join(difflib.unified_diff(
        original.decode("utf-8").splitlines(), patched.decode("utf-8").splitlines(),
        fromfile=f"original/{classname}.cpp", tofile=f"audit/{classname}.cpp", lineterm="")) + "\n"
    return patched, diff.encode("utf-8")


def expected_tree(original_root: Path) -> tuple[dict[str, bytes], dict]:
    originals, source_manifest = read_originals(original_root)
    files = {f"originals/{name}": data for name, data in originals.items()}
    corrections = [
        ("NXDNSACCH.cpp", "CNXDNSACCH", "getRAN", [
            (b"unsigned char temp2[9U];", b"unsigned char temp2[9U] = {};"),
            (b"unsigned char temp3[8U];", b"unsigned char temp3[8U] = {};"),
        ]),
        ("NXDNFACCH1.cpp", "CNXDNFACCH1", "getData", [
            (b"unsigned char temp2[24U];", b"unsigned char temp2[24U] = {};"),
            (b"unsigned char temp3[18U];", b"unsigned char temp3[18U] = {};"),
            (b"if (i != PUNCTURE_LIST[index])", b"if (index >= 48U || i != PUNCTURE_LIST[index])"),
        ]),
    ]
    correction_metadata = []
    for filename, classname, next_method, edits in corrections:
        original = originals[f"MMDVM-Host/{filename}"]
        patched, diff = patch_encode(original, classname, next_method, edits)
        files[f"generated/{filename}"] = patched
        files[f"generated/{filename}.patch"] = diff
        correction_metadata.append({
            "path": f"generated/{filename}", "replacement_count": len(edits),
            "original_sha256": sha(original), "patched_sha256": sha(patched),
            "diff_sha256": sha(diff),
            "replacements": [{"before": a.decode("ascii"), "after": b.decode("ascii")}
                             for a, b in edits],
        })
    control = originals["MMDVM-Host/NXDNControl.cpp"]
    declarations = re.findall(rb"const unsigned char SCRAMBLER\[\] = \{[^}]+\};", control)
    if len(declarations) != 1:
        raise ValueError("host whitening declaration is ambiguous")
    declaration = declarations[0]
    mask = bytes(int(value, 16) for value in re.findall(rb"0x([0-9A-Fa-f]{2})U", declaration))
    if len(mask) != 48 or mask[0] != 0 or mask[1] != 0 or mask[2] & 0xF0:
        raise ValueError("host whitening mask dimensions or sync preservation changed")
    if not control.startswith(b"/*") or b"*/" not in control:
        raise ValueError("host copyright notice not found")
    notice = control[:control.index(b"*/") + 2].decode("utf-8").replace("\r\n", "\n")
    declaration_text = declaration.decode("ascii").replace("\r\n", "\n").replace(
        "const unsigned char SCRAMBLER[]", "inline constexpr unsigned char kWhitening[48]")
    header = (notice + "\n\n// Exact declaration from pinned NXDNControl.cpp, commit " + PIN
              + ".\n// Channel whitening only; original source and license are retained.\n"
              + "#pragma once\nnamespace xerax_primary {\n" + declaration_text
              + "\n}  // namespace xerax_primary\n")
    files["generated/primary_whitening.h"] = header.encode("utf-8")
    support_path = Path(__file__).resolve().parents[1] / "nxdn_voice_words_v1" / "primary_support.cpp"
    support = support_path.read_bytes()
    if sha(support) != SUPPORT_SHA256:
        raise ValueError("previous pinned countBits support source changed")
    files["support/primary_support.cpp"] = support
    metadata = {
        "schema": 1, "kind": "nxdn_air_primary_source_preparation",
        "primary_manifest_sha256": PRIMARY_MANIFEST_SHA256,
        "prepare_script_sha256": sha(Path(__file__).read_bytes()),
        "original_source_files": 36, "original_api_metadata_files": 6,
        "original_repositories": source_manifest["repositories"],
        "corrections": correction_metadata, "total_replacements": 5,
        "support_sha256": SUPPORT_SHA256,
        "whitening_mask_sha256": sha(mask),
        "whitening_declaration_sha256": sha(declaration),
        "files": {name: {"bytes": len(data), "sha256": sha(data)}
                  for name, data in sorted(files.items())},
        "scope": "Source copies only; no native encoding, building, or frame corpus generation",
    }
    return files, metadata


def encoded_manifest(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def verify(destination: Path) -> dict:
    files, metadata = expected_tree(destination / "originals")
    for name, data in files.items():
        path = destination / name
        if not path.resolve().is_relative_to(destination.resolve()) or path.read_bytes() != data:
            raise ValueError(f"prepared source identity mismatch: {name}")
    if (destination / "manifest.json").read_bytes() != encoded_manifest(metadata):
        raise ValueError("prepared manifest identity mismatch")
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if actual != set(files) | {"manifest.json"}:
        raise ValueError("unexpected prepared file inventory")
    return metadata


def prepare(cache: Path, destination: Path) -> dict:
    cache = cache.resolve()
    destination = destination.absolute()
    resolved_destination = destination.resolve()
    if resolved_destination.is_relative_to(cache) or cache.is_relative_to(resolved_destination):
        raise ValueError("prepared directory must be separate from primary cache")
    if destination.exists() or destination.is_symlink():
        raise ValueError("refusing existing prepared directory")
    files, metadata = expected_tree(cache)
    destination.mkdir(parents=True, exist_ok=False)
    # No cleanup on error: a partial preparation remains as failed evidence.
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
    with (destination / "manifest.json").open("xb") as output:
        output.write(encoded_manifest(metadata))
    current_originals, _ = read_originals(cache)
    for name, data in current_originals.items():
        if files[f"originals/{name}"] != data:
            raise ValueError("primary cache changed during preparation")
    return verify(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--verify", type=Path, metavar="PREPARED_DIRECTORY")
    args = parser.parse_args()
    try:
        if args.verify is not None:
            if args.paths:
                raise ValueError("--verify does not accept positional paths")
            result = verify(args.verify)
        else:
            if len(args.paths) != 2:
                raise ValueError("usage: prepare_build.py PRIMARY_CACHE NEW_PREPARED_DIRECTORY")
            result = prepare(args.paths[0], args.paths[1])
        print(json.dumps({"verified": True, "files": len(result["files"]),
                          "total_replacements": result["total_replacements"]}))
        return 0
    except Exception as error:
        print(json.dumps({"verified": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
