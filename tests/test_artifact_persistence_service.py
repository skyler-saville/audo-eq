from audo_eq.application.artifact_persistence_service import PersistMasteredArtifact
from audo_eq.application.mastered_artifact_repository import (
    ArtifactPersistenceError,
    PersistenceGuarantee,
    PersistenceMode,
    PersistencePolicy,
    PersistedArtifact,
)


class _Repo:
    def __init__(self, result: PersistedArtifact):
        self._result = result

    def persist(self, **kwargs):
        return self._result


def test_guaranteed_immediate_requires_stored_status() -> None:
    service = PersistMasteredArtifact(repository=_Repo(PersistedArtifact(status="skipped")))

    try:
        service.run(
            object_name="mastered/file.wav",
            audio_bytes=b"abc",
            content_type="audio/wav",
            policy=PersistencePolicy(mode=PersistenceMode.IMMEDIATE, guarantee=PersistenceGuarantee.GUARANTEED),
        )
    except ArtifactPersistenceError:
        pass
    else:
        raise AssertionError("expected guaranteed immediate policy to raise")


def test_guaranteed_deferred_accepts_deferred_status() -> None:
    service = PersistMasteredArtifact(repository=_Repo(PersistedArtifact(status="deferred")))

    result = service.run(
        object_name="mastered/file.wav",
        audio_bytes=b"abc",
        content_type="audio/wav",
        policy=PersistencePolicy(mode=PersistenceMode.DEFERRED, guarantee=PersistenceGuarantee.GUARANTEED),
    )

    assert result.status == "deferred"
