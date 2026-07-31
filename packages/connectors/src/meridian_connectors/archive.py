"""Immutable local raw-payload archive.

Payloads land under <root>/<source_name>/<sha256>.raw and are addressed by
file:// URIs. Content addressing makes re-archiving the same payload a no-op
(dedupe), and existing files are never overwritten. Artifact ids are UUID5 of
(source_name, checksum) so the same payload always maps to the same id.
"""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from meridian_domain.enums import LicenseClass
from meridian_domain.models import SourceArtifactMeta

_ARTIFACT_NAMESPACE = uuid.UUID("6b7a1e6e-6f0f-4b9e-9f0e-3f6a2b8c4d5e")


class ArchiveIntegrityError(Exception):
    """An existing archived file no longer matches its checksum."""


def artifact_id(source_name: str, checksum_sha256: str) -> uuid.UUID:
    return uuid.uuid5(_ARTIFACT_NAMESPACE, f"{source_name}:{checksum_sha256}")


class RawArchive:
    def __init__(self, root: Path) -> None:
        self._root = root

    def archive(
        self,
        *,
        source_name: str,
        payload: bytes,
        retrieved_at: datetime,
        knowledge_timestamp: datetime,
        license_class: LicenseClass,
        source_uri: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SourceArtifactMeta:
        checksum = hashlib.sha256(payload).hexdigest()
        target_dir = self._root / source_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{checksum}.raw"

        if target.exists():
            existing = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing != checksum:
                raise ArchiveIntegrityError(
                    f"{target} exists but its content hash {existing} != {checksum}"
                )
            # Identical payload already archived: dedupe, never rewrite.
        else:
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(payload)
            tmp.rename(target)

        return SourceArtifactMeta(
            id=artifact_id(source_name, checksum),
            source_name=source_name,
            source_uri=source_uri,
            retrieved_at=retrieved_at,
            knowledge_timestamp=knowledge_timestamp,
            checksum_sha256=checksum,
            license_class=license_class,
            object_uri=target.resolve().as_uri(),
            metadata=dict(metadata or {}),
        )
