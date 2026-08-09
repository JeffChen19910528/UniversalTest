"""Central, bounded manifest reader.

Every detector needs to look at a handful of well-known manifest files
(`package.json`, `pyproject.toml`, `*.csproj`, ...). Reading and parsing them
once here — instead of each detector re-scanning the tree — keeps discovery
fast, predictable, and easy to extend with one maintainable method rather
than ad hoc per-detector file reads.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from universal_test.discovery.filesystem import ScannedFile, read_text_safe


@dataclass
class ManifestBundle:
    root: Path
    files: list[ScannedFile]

    package_json: dict | None = None
    package_json_text: str | None = None
    pyproject: dict | None = None
    requirements_txt: str = ""
    csproj_texts: list[str] = field(default_factory=list)
    sln_texts: list[str] = field(default_factory=list)
    pom_xml: str | None = None
    build_gradle: str = ""
    composer_json: dict | None = None
    go_mod: str | None = None
    cargo_toml: dict | None = None
    parse_warnings: list[str] = field(default_factory=list)

    def by_name(self, *names: str) -> list[ScannedFile]:
        lowered = {n.lower() for n in names}
        return [f for f in self.files if Path(f.relative).name.lower() in lowered]

    def by_suffix(self, *suffixes: str) -> list[ScannedFile]:
        lowered = tuple(s.lower() for s in suffixes)
        return [f for f in self.files if f.relative.lower().endswith(lowered)]


def load_manifests(root: Path, files: list[ScannedFile]) -> ManifestBundle:
    bundle = ManifestBundle(root=root, files=files)

    for f in bundle.by_name("package.json"):
        text = read_text_safe(f.path)
        if text is None:
            continue
        bundle.package_json_text = text
        try:
            bundle.package_json = json.loads(text)
        except json.JSONDecodeError as exc:
            bundle.parse_warnings.append(f"could not parse {f.relative}: {exc}")

    for f in bundle.by_name("pyproject.toml"):
        try:
            with open(f.path, "rb") as fh:
                bundle.pyproject = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            bundle.parse_warnings.append(f"could not parse {f.relative}: {exc}")

    for f in bundle.by_name("requirements.txt", "requirements-dev.txt", "requirements-test.txt"):
        text = read_text_safe(f.path)
        if text:
            bundle.requirements_txt += "\n" + text

    for f in bundle.by_suffix(".csproj"):
        text = read_text_safe(f.path)
        if text:
            bundle.csproj_texts.append(text)

    for f in bundle.by_suffix(".sln"):
        text = read_text_safe(f.path)
        if text:
            bundle.sln_texts.append(text)

    pom_files = bundle.by_name("pom.xml")
    if pom_files:
        bundle.pom_xml = read_text_safe(pom_files[0].path) or ""

    for f in bundle.by_name("build.gradle", "build.gradle.kts"):
        text = read_text_safe(f.path)
        if text:
            bundle.build_gradle += "\n" + text

    composer_files = bundle.by_name("composer.json")
    if composer_files:
        text = read_text_safe(composer_files[0].path)
        if text:
            try:
                bundle.composer_json = json.loads(text)
            except json.JSONDecodeError as exc:
                bundle.parse_warnings.append(f"could not parse composer.json: {exc}")

    go_mod_files = bundle.by_name("go.mod")
    if go_mod_files:
        bundle.go_mod = read_text_safe(go_mod_files[0].path)

    cargo_files = bundle.by_name("cargo.toml")
    if cargo_files:
        try:
            with open(cargo_files[0].path, "rb") as fh:
                bundle.cargo_toml = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            bundle.parse_warnings.append(f"could not parse Cargo.toml: {exc}")

    return bundle


def npm_dependency_names(bundle: ManifestBundle) -> set[str]:
    if not bundle.package_json:
        return set()
    names: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        section_data = bundle.package_json.get(section)
        if isinstance(section_data, dict):
            names.update(section_data.keys())
    return names


def python_dependency_names(bundle: ManifestBundle) -> set[str]:
    names: set[str] = set()
    for line in bundle.requirements_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            if sep in line:
                line = line.split(sep, 1)[0]
                break
        if line:
            names.add(line.strip().lower())

    if bundle.pyproject:
        deps: list[str] = []
        project = bundle.pyproject.get("project", {})
        if isinstance(project, dict):
            deps.extend(project.get("dependencies", []) or [])
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for group in optional.values():
                    deps.extend(group or [])
        poetry = bundle.pyproject.get("tool", {}).get("poetry", {}) if isinstance(
            bundle.pyproject.get("tool"), dict
        ) else {}
        if isinstance(poetry, dict):
            for section in ("dependencies", "dev-dependencies"):
                section_data = poetry.get(section)
                if isinstance(section_data, dict):
                    deps.extend(section_data.keys())
        for dep in deps:
            name = dep
            for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", " "):
                if sep in name:
                    name = name.split(sep, 1)[0]
                    break
            if name:
                names.add(name.strip().lower())

    return names
