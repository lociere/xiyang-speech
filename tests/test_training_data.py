import csv
import json
import wave

import pytest

from training.prepare import FIELDS, prepare


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


def test_export_keeps_holdout_sets_and_format_consistent(tmp_path):
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
        assert str(tmp_path / "wav24k" / (record["key"] + ".wav")) in scp
        assert "<|endofprompt|>" in (tmp_path / "tts" / split / "instruct").read_text()
    assert len(set(ids)) == 3


def test_unreviewed_transcriptions_require_explicit_preview(tmp_path):
    labels = fixture_labels(tmp_path, checked="no")
    with pytest.raises(ValueError, match="checked"):
        prepare(labels, tmp_path)
    prepare(labels, tmp_path, allow_unreviewed=True)
    assert len(json.loads((tmp_path / "preparation.json").read_text())["unchecked"]) == 3
