import tempfile
import unittest
from pathlib import Path
from unittest import mock

import transcribe


class FakeSegment:
    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end
        self.duration = max(0.0, end - start)

    def __and__(self, other):
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return FakeSegment(start, end)


class FakeDiarization:
    def __init__(self, tracks):
        self._tracks = tracks

    def itertracks(self, yield_label=False):
        for turn, speaker in self._tracks:
            if yield_label:
                yield turn, None, speaker
            else:
                yield turn, None


class TranscribeTests(unittest.TestCase):
    def test_format_timestamp_rounds_across_second_boundary(self):
        self.assertEqual(transcribe.format_timestamp(0), "00:00:00,000")
        self.assertEqual(transcribe.format_timestamp(61.234), "00:01:01,234")
        self.assertEqual(transcribe.format_timestamp(59.9996), "00:01:00,000")

    def test_setup_output_folder_handles_nested_and_non_nested_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "meeting.m4a"
            audio.write_text("audio", encoding="utf-8")

            _, output_folder, _, _ = transcribe.setup_output_folder(str(audio))
            self.assertEqual(Path(output_folder).resolve(), (root / "meeting").resolve())

            nested = root / "meeting" / "meeting.wav"
            nested.parent.mkdir(exist_ok=True)
            nested.write_text("audio", encoding="utf-8")

            _, nested_output_folder, _, _ = transcribe.setup_output_folder(str(nested))
            self.assertEqual(Path(nested_output_folder).resolve(), nested.parent.resolve())

    def test_setup_output_folder_uses_custom_output_root_when_provided(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "demo.wav"
            audio.write_text("audio", encoding="utf-8")
            custom_root = root / "exports"

            _, output_folder, _, _ = transcribe.setup_output_folder(
                str(audio), output_root_dir=str(custom_root)
            )

            self.assertEqual(Path(output_folder).resolve(), (custom_root / "demo").resolve())

    def test_merge_transcription_and_diarization_picks_primary_speaker(self):
        whisper_segments = [
            {"start": 0.0, "end": 2.0, "text": "hello"},
            {"start": 2.0, "end": 4.0, "text": "world"},
            {"start": 5.0, "end": 6.0, "text": "nobody"},
        ]

        diarization = FakeDiarization(
            [
                (FakeSegment(0.0, 1.7), "SPEAKER_01"),
                (FakeSegment(1.7, 2.0), "SPEAKER_02"),
                (FakeSegment(2.0, 3.3), "SPEAKER_02"),
                (FakeSegment(3.3, 4.0), "SPEAKER_01"),
            ]
        )

        with mock.patch.object(transcribe, "_load_segment_class", return_value=FakeSegment):
            merged = transcribe.merge_transcription_and_diarization(whisper_segments, diarization)

        self.assertEqual(merged[0]["speaker"], "SPEAKER_01")
        self.assertEqual(merged[1]["speaker"], "SPEAKER_02")
        self.assertEqual(merged[2]["speaker"], "Unknown")

    def test_run_pipeline_saves_plain_outputs_without_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "sample.wav"
            audio.write_text("audio", encoding="utf-8")
            custom_output_root = root / "out"

            transcription_result = {
                "text": "transcribed text",
                "segments": [{"start": 0.0, "end": 1.0, "text": "transcribed text"}],
            }

            with mock.patch.object(transcribe, "transcribe_audio", return_value=transcription_result):
                result = transcribe.run_pipeline(
                    audio_file=str(audio),
                    model="turbo",
                    prompt="prompt",
                    language="en",
                    hf_token="",
                    clean_audio=False,
                    diarization=True,
                    move_original_file=False,
                    output_root_dir=str(custom_output_root),
                    verbose=False,
                )

            self.assertFalse(result["is_diarized"])
            save_prefix = Path(result["save_prefix"])
            self.assertEqual(save_prefix.parent.resolve(), (custom_output_root / "sample").resolve())
            self.assertTrue(save_prefix.with_suffix(".txt").exists())
            self.assertTrue(save_prefix.with_suffix(".srt").exists())

    def test_run_pipeline_continues_when_clean_audio_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "fallback.wav"
            audio.write_text("audio", encoding="utf-8")

            transcription_result = {
                "text": "fallback transcription",
                "segments": [{"start": 0.0, "end": 1.0, "text": "fallback transcription"}],
            }

            with mock.patch.object(transcribe, "clean_audio_deepfilternet", return_value=None):
                with mock.patch.object(transcribe, "transcribe_audio", return_value=transcription_result) as tx_mock:
                    result = transcribe.run_pipeline(
                        audio_file=str(audio),
                        clean_audio=True,
                        diarization=False,
                        move_original_file=False,
                        verbose=False,
                    )

            tx_mock.assert_called_once()
            transcribed_path = Path(tx_mock.call_args.args[0]).resolve()
            self.assertEqual(transcribed_path, audio.resolve())
            self.assertEqual(result["text"], "fallback transcription")

    def test_run_pipeline_moves_original_audio_into_output_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "session.mp3"
            audio.write_text("audio", encoding="utf-8")

            transcription_result = {
                "text": "ok",
                "segments": [{"start": 0.0, "end": 1.0, "text": "ok"}],
            }

            with mock.patch.object(transcribe, "transcribe_audio", return_value=transcription_result):
                result = transcribe.run_pipeline(
                    audio_file=str(audio),
                    clean_audio=False,
                    diarization=False,
                    move_original_file=True,
                    verbose=False,
                )

            moved_path = Path(result["source_audio"])
            self.assertTrue(moved_path.exists())
            self.assertFalse(audio.exists())
            self.assertEqual(moved_path.parent, Path(result["output_folder"]))


if __name__ == "__main__":
    unittest.main()
