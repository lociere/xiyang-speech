import csv
import json
import shutil
import wave
from pathlib import Path

import pytest

from training.prepare import FIELDS, prepare
import training.prepare as preparation


def fixture_labels(tmp_path, checked="yes"):
    labels = tmp_path / "labels.tsv"
    with labels.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        for index, split in enumerate(("train", "dev", "test")):
            key = f"xy{index:03d}"
            source = tmp_path / f"{key}.wav"
            for path, rate in ((source, 16000), (tmp_path / "wav16k" / source.name, 16000),
                               (tmp_path / "wav24k" / source.name, 24000)):
                path.parent.mkdir(exist_ok=True)
                with wave.open(str(path), "wb") as audio:
                    audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\x00\x00" * rate * 2)
            writer.writerow(dict(id=key, source=source.name, text="你好，昔阳。", split=split,
                                 checked=checked))
    return labels


def test_export_keeps_holdout_sets_and_format_consistent(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, "ROOT", tmp_path)
    labels = fixture_labels(tmp_path)
    prepare(labels, tmp_path)
    ids = []
    for split in ("train", "dev", "test"):
        record = json.loads((tmp_path / "asr" / f"{split}.jsonl").read_text())
        ids.append(record["key"])
        assert record["speech_length"] == 200
        assert record["messages"][2]["content"] == "你好，昔阳。"
        scp = (tmp_path / "tts" / split / "wav.scp").read_text()
        assert scp.startswith(record["key"] + " ")
        assert f"wav24k/{record['key']}.wav" in scp
        assert "<|endofprompt|>" in (tmp_path / "tts" / split / "instruct").read_text()
    assert len(set(ids)) == 3


def test_exported_paths_survive_repository_relocation(tmp_path, monkeypatch):
    original = tmp_path / "original"
    original.mkdir()
    monkeypatch.setattr(preparation, "ROOT", original)
    prepare(fixture_labels(original), original)
    moved = tmp_path / "other-user" / "checkout"
    shutil.copytree(original, moved)
    shutil.rmtree(original)
    for split in ("train", "dev", "test"):
        record = json.loads((moved / "asr" / f"{split}.jsonl").read_text())
        content = record["messages"][1]["content"]
        audio = content.split("<|startofspeech|>!", 1)[1].split("<|endofspeech|>", 1)[0]
        scp_audio = (moved / "tts" / split / "wav.scp").read_text().split(maxsplit=1)[1].strip()
        for value in (audio, scp_audio):
            assert not Path(value).is_absolute()
            with wave.open(str(moved / value)) as stream:
                assert stream.getnframes() > 0


def test_unreviewed_transcriptions_require_explicit_preview(tmp_path):
    labels = fixture_labels(tmp_path, checked="no")
    with pytest.raises(ValueError, match="checked"):
        prepare(labels, tmp_path)
    prepare(labels, tmp_path, allow_unreviewed=True)
    assert len(json.loads((tmp_path / "preparation.json").read_text())["unchecked"]) == 3
