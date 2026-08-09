"""Database evidence detection — static evidence only, never connects to anything
(skill.md §6, Phase 2 constraint list item 5).
"""

from __future__ import annotations

import re

from universal_test.core.models.enums import DetectionConfidence
from universal_test.core.models.evidence import Evidence
from universal_test.discovery.filesystem import ScannedFile, read_text_safe
from universal_test.discovery.manifests import ManifestBundle, npm_dependency_names, python_dependency_names
from universal_test.discovery.models import DatabaseDetection

_NPM_PACKAGES = {
    "PostgreSQL": {"pg", "postgres", "postgres-js", "typeorm"},
    "MySQL": {"mysql", "mysql2"},
    "SQL Server": {"mssql", "tedious"},
    "SQLite": {"sqlite3", "better-sqlite3"},
    "MongoDB": {"mongodb", "mongoose"},
    "Redis": {"redis", "ioredis"},
}

_PYTHON_PACKAGES = {
    "PostgreSQL": {"psycopg2", "psycopg2-binary", "asyncpg"},
    "MySQL": {"pymysql", "mysqlclient", "mysql-connector-python"},
    "SQL Server": {"pyodbc", "pymssql"},
    "MongoDB": {"pymongo", "motor"},
    "Redis": {"redis"},
}

_CSPROJ_PACKAGES = {
    "PostgreSQL": ("npgsql",),
    "MySQL": ("mysql.data", "mysqlconnector"),
    "SQL Server": ("system.data.sqlclient", "microsoft.data.sqlclient", "microsoft.entityframeworkcore.sqlserver"),
    "SQLite": ("microsoft.entityframeworkcore.sqlite", "system.data.sqlite"),
    "MongoDB": ("mongodb.driver",),
    "Redis": ("stackexchange.redis",),
}

_CONNECTION_STRING_PATTERNS = {
    "PostgreSQL": re.compile(r"postgres(?:ql)?://", re.IGNORECASE),
    "MySQL": re.compile(r"mysql://", re.IGNORECASE),
    "MongoDB": re.compile(r"mongodb(?:\+srv)?://", re.IGNORECASE),
    "Redis": re.compile(r"redis://", re.IGNORECASE),
    "SQL Server": re.compile(r"(?i)(Server=|Data Source=).*(Database=|Initial Catalog=)"),
}

_CONFIG_FILE_NAMES = {
    "appsettings.json", "appsettings.development.json", ".env", ".env.example",
    "application.properties", "application.yml", "application.yaml", "config.py",
    "settings.py", "database.yml",
}

_COMPOSE_FILE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}

_COMPOSE_IMAGE_PATTERNS = {
    "PostgreSQL": re.compile(r"(?i)image:\s*[\"']?[\w./-]*postgres"),
    "MySQL": re.compile(r"(?i)image:\s*[\"']?[\w./-]*mysql"),
    "MongoDB": re.compile(r"(?i)image:\s*[\"']?[\w./-]*mongo"),
    "Redis": re.compile(r"(?i)image:\s*[\"']?[\w./-]*redis"),
    "SQL Server": re.compile(r"(?i)image:\s*[\"']?[\w./-]*mssql"),
}


def detect_databases(files: list[ScannedFile], manifests: ManifestBundle) -> list[DatabaseDetection]:
    found: dict[str, list[Evidence]] = {}

    npm_deps = npm_dependency_names(manifests)
    for db, packages in _NPM_PACKAGES.items():
        matched = npm_deps & packages
        if matched:
            found.setdefault(db, []).append(Evidence("dependency", {"source": "package.json", "matched": sorted(matched)}))

    python_deps = python_dependency_names(manifests)
    for db, packages in _PYTHON_PACKAGES.items():
        matched = python_deps & packages
        if matched:
            found.setdefault(db, []).append(Evidence("dependency", {"source": "requirements.txt/pyproject.toml", "matched": sorted(matched)}))

    for csproj_text, csproj_file in zip(manifests.csproj_texts, manifests.by_suffix(".csproj")):
        lowered = csproj_text.lower()
        for db, packages in _CSPROJ_PACKAGES.items():
            for package in packages:
                if package in lowered:
                    found.setdefault(db, []).append(Evidence("dependency", {"source": csproj_file.relative, "matched": package}))

    sqlite_files = [f for f in files if f.extension in (".sqlite", ".sqlite3", ".db")]
    if sqlite_files:
        found.setdefault("SQLite", []).append(Evidence("file", {"files": [f.relative for f in sqlite_files[:5]]}))

    for f in files:
        if f.path.name.lower() not in _CONFIG_FILE_NAMES and not f.relative.lower().endswith((".env", ".env.example")):
            continue
        text = read_text_safe(f.path)
        if not text:
            continue
        for db, pattern in _CONNECTION_STRING_PATTERNS.items():
            if pattern.search(text):
                found.setdefault(db, []).append(Evidence("connection_string_pattern", {"file": f.relative}))

    for f in files:
        if f.path.name.lower() not in _COMPOSE_FILE_NAMES:
            continue
        text = read_text_safe(f.path)
        if not text:
            continue
        for db, pattern in _COMPOSE_IMAGE_PATTERNS.items():
            if pattern.search(text):
                found.setdefault(db, []).append(Evidence("compose_service_image", {"file": f.relative}))

    detections = [
        DatabaseDetection(name=db, confidence=DetectionConfidence.DETECTED, evidence=evidence)
        for db, evidence in found.items()
    ]
    detections.sort(key=lambda d: d.name)
    return detections
