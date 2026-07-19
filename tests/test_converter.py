from __future__ import annotations

import gzip
import io
import json
import wave
from pathlib import Path

import fitz
import pytest
from docx import Document
from PIL import Image

from app import app
from converter import ConversionManager, output_filename


@pytest.fixture()
def manager() -> ConversionManager:
    return ConversionManager()


def test_output_filename_preserves_name_and_handles_collision():
    used: set[str] = set()
    assert output_filename("My holiday.photo.JPG", "webp", used) == "My holiday.photo.webp"
    assert output_filename("My holiday.photo.png", "webp", used) == "My holiday.photo (2).webp"


def test_image_conversion(manager: ConversionManager, tmp_path: Path):
    source = tmp_path / "sample.png"
    output = tmp_path / "sample.webp"
    Image.new("RGBA", (48, 32), (42, 160, 92, 180)).save(source)

    manager.convert(source, "png", output, "webp")

    with Image.open(output) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (48, 32)


def test_all_static_image_outputs_are_readable(manager: ConversionManager, tmp_path: Path):
    source = tmp_path / "tiny.png"
    Image.new("RGBA", (12, 8), (42, 160, 92, 180)).save(source)

    for target in ("png", "jpg", "webp", "bmp", "tiff", "ico"):
        output = tmp_path / f"tiny.{target}"
        manager.convert(source, "png", output, target)
        with Image.open(output) as converted:
            converted.verify()

    pdf_output = tmp_path / "tiny.pdf"
    manager.convert(source, "png", pdf_output, "pdf")
    with fitz.open(pdf_output) as converted_pdf:
        assert len(converted_pdf) == 1


def test_pdf_to_word_and_word_to_pdf(manager: ConversionManager, tmp_path: Path):
    source_pdf = tmp_path / "source.pdf"
    output_docx = tmp_path / "source.docx"
    roundtrip_pdf = tmp_path / "roundtrip.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 90), "Local conversion works")
    pdf.save(source_pdf)
    pdf.close()

    manager.convert(source_pdf, "pdf", output_docx, "docx")
    assert "Local conversion works" in "\n".join(p.text for p in Document(output_docx).paragraphs)

    manager.convert(output_docx, "docx", roundtrip_pdf, "pdf")
    with fitz.open(roundtrip_pdf) as converted:
        assert "Local conversion works" in "".join(page.get_text() for page in converted)


def test_lottie_json_tgs_roundtrip(manager: ConversionManager, tmp_path: Path):
    animation = {"v": "5.7.4", "fr": 30, "ip": 0, "op": 10, "w": 32, "h": 32, "layers": []}
    source_json = tmp_path / "sticker.json"
    tgs = tmp_path / "sticker.tgs"
    output_json = tmp_path / "sticker-output.json"
    source_json.write_text(json.dumps(animation), encoding="utf-8")

    manager.convert(source_json, "json", tgs, "tgs")
    with gzip.open(tgs, "rt", encoding="utf-8") as compressed:
        assert json.load(compressed)["fr"] == 30

    manager.convert(tgs, "tgs", output_json, "json")
    assert json.loads(output_json.read_text(encoding="utf-8"))["layers"] == []


def test_audio_conversion_when_ffmpeg_is_available(manager: ConversionManager, tmp_path: Path):
    if not manager.ffmpeg:
        pytest.skip("FFmpeg is unavailable")
    source = tmp_path / "tone.wav"
    output = tmp_path / "tone.mp3"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 4000)

    manager.convert(source, "wav", output, "mp3")
    assert output.stat().st_size > 100


def test_animated_gif_to_mp4_and_webm(manager: ConversionManager, tmp_path: Path):
    if not manager.ffmpeg:
        pytest.skip("FFmpeg is unavailable")
    source = tmp_path / "motion.gif"
    frames = [Image.new("RGB", (32, 24), color) for color in ("#c9f45b", "#ff735c")]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)

    for target in ("mp4", "webm"):
        output = tmp_path / f"motion.{target}"
        manager.convert(source, "gif", output, target)
        assert output.stat().st_size > 100


def test_webp_to_video_and_expanded_media_outputs(manager: ConversionManager, tmp_path: Path):
    if not manager.ffmpeg:
        pytest.skip("FFmpeg is unavailable")
    source = tmp_path / "still.webp"
    Image.new("RGB", (64, 48), "#ff735c").save(source, "WEBP")

    generated_videos = {}
    for target in ("mp4", "webm"):
        output = tmp_path / f"still.{target}"
        note = manager.convert(source, "webp", output, target)
        assert output.stat().st_size > 100
        assert "three-second" in note
        generated_videos[target] = output

    icon_source = tmp_path / "icon.ico"
    Image.new("RGBA", (32, 32), "#c9f45b").save(icon_source, "ICO", sizes=[(32, 32)])
    icon_video = tmp_path / "icon.webm"
    manager.convert(icon_source, "ico", icon_video, "webm")
    assert icon_video.stat().st_size > 100

    for target in ("avi", "m4v", "mpeg", "3gp", "gif"):
        output = tmp_path / f"video.{target}"
        manager.convert(generated_videos["mp4"], "mp4", output, target)
        assert output.stat().st_size > 100

    for target in ("png", "jpg", "webp"):
        output = tmp_path / f"first-frame.{target}"
        note = manager.convert(generated_videos["mp4"], "mp4", output, target)
        assert "first video frame" in note
        with Image.open(output) as frame:
            frame.verify()


def test_wma_is_available_as_an_audio_output(manager: ConversionManager, tmp_path: Path):
    if not manager.ffmpeg:
        pytest.skip("FFmpeg is unavailable")
    source = tmp_path / "tone.wav"
    output = tmp_path / "tone.wma"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 8000)

    manager.convert(source, "wav", output, "wma")
    assert output.stat().st_size > 100


def test_mixed_batch_api_keeps_base_names(tmp_path: Path):
    image_data = io.BytesIO()
    Image.new("RGB", (12, 12), "#ee735c").save(image_data, "PNG")
    image_data.seek(0)

    with app.test_client() as client:
        response = client.post(
            "/api/convert",
            data={
                "files": [
                    (image_data, "Cover Art.png"),
                    (io.BytesIO(b"hello locally"), "Notes.txt"),
                ],
                "targets": ["webp", "pdf"],
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success_count"] == 2
        assert [item["output_name"] for item in payload["results"]] == [
            "Cover Art.webp",
            "Notes.pdf",
        ]
        assert payload["download_all_url"]

        archive = client.get(payload["download_all_url"])
        assert archive.status_code == 200
        assert archive.data.startswith(b"PK")
        client.delete(f"/api/jobs/{payload['job_id']}")
