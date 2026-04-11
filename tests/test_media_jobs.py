import pytest

from src.modules.media.media_jobs import MediaJobError, MediaJobManager


def test_friendly_job_error_for_music_without_audio_is_not_key_blame():
    manager = MediaJobManager()

    message = manager._friendly_job_error(
        "music",
        "A resposta do Lyria nao retornou audio. Resposta textual: blocked",
    )

    assert "sem audio" in message.lower() or "sem áudio" in message.lower()
    assert "chave" not in message.lower()


def test_video_generation_jobs_are_rejected():
    manager = MediaJobManager()

    with pytest.raises(MediaJobError):
        manager.submit("video", "trailer da Hana", "test")
