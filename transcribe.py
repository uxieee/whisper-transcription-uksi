import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

DEFAULT_PROMPT = "Ang sumusunod ay usapan sa Tagalog at English."
DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-3.1"

ProgressCallback = Optional[Callable[[str], None]]

_torch_module = None
_torch_patched = False


def _load_torch():
    global _torch_module, _torch_patched
    if _torch_module is None:
        import torch

        _torch_module = torch

    if not _torch_patched:
        original_load = _torch_module.load

        def safe_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return original_load(*args, **kwargs)

        _torch_module.load = safe_load
        _torch_patched = True

    return _torch_module


def _load_whisper_module():
    import whisper

    return whisper


def _load_segment_class():
    from pyannote.core import Segment

    return Segment


def _emit(message: str, callback: ProgressCallback = None, verbose: bool = True) -> None:
    if callback is not None:
        callback(message)
    elif verbose:
        print(message)


class ProgressSpinner:
    def __init__(self, message: str = "Processing", enabled: bool = True):
        self.message = message
        self.enabled = enabled
        self.stop_running = False
        self.thread = None

    def _animate(self):
        chars = "/-\\|"
        idx = 0
        start_time = time.time()
        while not self.stop_running:
            elapsed = int(time.time() - start_time)
            sys.stdout.write(f"\r{self.message} {chars[idx % len(chars)]} [Elapsed: {elapsed}s]   ")
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1
        total = int(time.time() - start_time)
        sys.stdout.write(f"\r{self.message} Done! [Total: {total}s]     \n")
        sys.stdout.flush()

    def __enter__(self):
        if self.enabled:
            self.stop_running = False
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.enabled and self.thread:
            self.stop_running = True
            self.thread.join()


def transcribe_audio(
    audio_path: str,
    model_size: str = "turbo",
    prompt: Optional[str] = None,
    language: Optional[str] = "tl",
    device: str = "cpu",
    verbose: bool = True,
):
    """Transcribe an audio file with OpenAI Whisper."""
    _emit(f"Loading Whisper model '{model_size}'...", verbose=verbose)

    try:
        _load_torch()
        whisper = _load_whisper_module()
        model = whisper.load_model(model_size, device=device)
    except Exception as exc:
        _emit(f"Error loading Whisper model: {exc}", verbose=verbose)
        return None

    decode_options = {
        "fp16": device == "cuda",
        "verbose": verbose,
    }

    normalized_language = None if language in (None, "", "auto") else language
    if normalized_language:
        decode_options["language"] = normalized_language
    if prompt:
        decode_options["initial_prompt"] = prompt

    _emit(f"Transcribing '{audio_path}'...", verbose=verbose)
    try:
        result = model.transcribe(audio_path, **decode_options)
    except Exception as exc:
        _emit(f"Error during transcription: {exc}", verbose=verbose)
        return None

    return result


def _load_diarization_pipeline(hf_token: str, device: str = "cpu"):
    _load_torch()
    from pyannote.audio import Pipeline

    os.environ["HF_TOKEN"] = hf_token

    try:
        pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL_ID, use_auth_token=hf_token)
    except TypeError:
        pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL_ID, token=hf_token)

    if device in {"cuda", "mps"}:
        torch = _load_torch()
        pipeline.to(torch.device(device))

    return pipeline


def diarize_audio(audio_path: str, hf_token: str, device: str = "cpu", verbose: bool = True):
    """Perform speaker diarization with pyannote.audio."""
    if not hf_token:
        _emit("No Hugging Face token provided. Skipping diarization.", verbose=verbose)
        return None

    _emit("Loading pyannote diarization pipeline...", verbose=verbose)
    try:
        pipeline = _load_diarization_pipeline(hf_token=hf_token, device=device)
    except Exception as exc:
        _emit(f"Error loading diarization pipeline: {exc}", verbose=verbose)
        return None

    _emit(f"Running diarization for '{audio_path}'...", verbose=verbose)
    try:
        with ProgressSpinner("Diarizing", enabled=verbose):
            diarization = pipeline(audio_path)
    except Exception as exc:
        _emit(f"Error during diarization: {exc}", verbose=verbose)
        return None

    return diarization


def merge_transcription_and_diarization(whisper_segments, diarization):
    """Match Whisper segments to speakers by time overlap."""
    Segment = _load_segment_class()
    final_segments = []

    for seg in whisper_segments:
        start = float(seg["start"])
        end = float(seg["end"])
        if end <= start:
            end = start + 0.001

        whisper_segment = Segment(start, end)
        speakers = []

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            intersection = turn & whisper_segment
            if intersection.duration > 0:
                speakers.append((speaker, intersection.duration))

        if speakers:
            speakers.sort(key=lambda item: item[1], reverse=True)
            primary_speaker = speakers[0][0]
        else:
            primary_speaker = "Unknown"

        final_segments.append(
            {
                "start": start,
                "end": end,
                "speaker": primary_speaker,
                "text": seg.get("text", ""),
            }
        )

    return final_segments


def format_timestamp(seconds: float):
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remaining_ms = divmod(total_ms, 3600 * 1000)
    minutes, remaining_ms = divmod(remaining_ms, 60 * 1000)
    secs, millis = divmod(remaining_ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def save_to_file(text: str, segments: List[Dict], base_filename: str):
    txt_path = f"{base_filename}.txt"
    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"Saved transcription to: {txt_path}")

    srt_path = f"{base_filename}.srt"
    with open(srt_path, "w", encoding="utf-8") as handle:
        for idx, segment in enumerate(segments, start=1):
            start = format_timestamp(float(segment["start"]))
            end = format_timestamp(float(segment["end"]))
            text_segment = str(segment.get("text", "")).strip()
            handle.write(f"{idx}\n")
            handle.write(f"{start} --> {end}\n")
            handle.write(f"{text_segment}\n\n")

    print(f"Saved subtitles to: {srt_path}")


def save_diarized_output(segments: List[Dict], base_filename: str):
    txt_path = f"{base_filename}_diarized.txt"
    with open(txt_path, "w", encoding="utf-8") as handle:
        for seg in segments:
            handle.write(f"[{seg['speaker']}] {str(seg.get('text', '')).strip()}\n")

    print(f"Saved diarized text to: {txt_path}")

    srt_path = f"{base_filename}_diarized.srt"
    with open(srt_path, "w", encoding="utf-8") as handle:
        for idx, seg in enumerate(segments, start=1):
            start = format_timestamp(float(seg["start"]))
            end = format_timestamp(float(seg["end"]))
            text_segment = str(seg.get("text", "")).strip()
            handle.write(f"{idx}\n")
            handle.write(f"{start} --> {end}\n")
            handle.write(f"[{seg['speaker']}] {text_segment}\n\n")

    print(f"Saved diarized subtitles to: {srt_path}")


def _resolve_deepfilter_binary() -> Optional[str]:
    venv_bin = Path(sys.prefix) / "bin" / "deepFilter"
    if venv_bin.exists():
        return str(venv_bin)

    return shutil.which("deepFilter")


def clean_audio_deepfilternet(audio_path: str, output_dir: str):
    """Clean audio with DeepFilterNet and return generated file path."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print("Warning: 'ffmpeg' is not installed. Skipping audio cleaning.")
        return None

    deep_filter_bin = _resolve_deepfilter_binary()
    if not deep_filter_bin:
        print("Warning: 'deepFilter' is not installed. Skipping audio cleaning.")
        return None

    print("Enhancing audio with DeepFilterNet...")

    abs_audio_path = str(Path(audio_path).expanduser().resolve())
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    temp_wav = None
    working_audio = abs_audio_path
    before_files = {path.name for path in output_path.glob("*_DeepFilterNet3.wav")}

    try:
        if not abs_audio_path.lower().endswith(".wav"):
            stem = Path(abs_audio_path).stem
            temp_wav = output_path / f"{stem}.df_input.wav"
            print("Converting to temporary WAV for cleaning...")
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-i",
                    abs_audio_path,
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    str(temp_wav),
                    "-y",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            working_audio = str(temp_wav)

        subprocess.run(
            [deep_filter_bin, working_audio, "-o", str(output_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        after_files = list(output_path.glob("*_DeepFilterNet3.wav"))
        created_files = [path for path in after_files if path.name not in before_files]
        if created_files:
            created_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            cleaned_path = created_files[0]
            print(f"Audio cleaned: {cleaned_path}")
            return str(cleaned_path)

        expected = output_path / f"{Path(working_audio).stem}_DeepFilterNet3.wav"
        if expected.exists():
            print(f"Audio cleaned: {expected}")
            return str(expected)

        print("Warning: DeepFilterNet finished but output file was not found.")
        return None
    except FileNotFoundError as exc:
        print(f"Warning: Required binary not found: {exc}")
        return None
    except subprocess.CalledProcessError as exc:
        print(f"Warning: Audio cleaning failed: {exc}")
        return None
    finally:
        if temp_wav and temp_wav.exists():
            temp_wav.unlink()


def convert_to_wav(audio_path: str):
    """Convert audio to temporary WAV file for diarization compatibility."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print("Error converting to WAV: 'ffmpeg' is not installed.")
        return None

    source = Path(audio_path).expanduser().resolve()
    fd, temp_name = tempfile.mkstemp(
        suffix=".temp.wav",
        prefix=f"{source.stem}.",
        dir=str(source.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    temp_path.unlink(missing_ok=True)

    print(f"Converting '{audio_path}' to WAV for processing...")
    try:
        subprocess.run(
            [
                ffmpeg_bin,
                "-i",
                str(source),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(temp_path),
                "-y",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return str(temp_path)
    except subprocess.CalledProcessError as exc:
        print(f"Error converting to WAV: {exc}")
        temp_path.unlink(missing_ok=True)
        return None


def setup_output_folder(audio_file_path: str, output_root_dir: Optional[str] = None):
    """Create output folder and return normalized path details."""
    abs_audio_path = str(Path(audio_file_path).expanduser().resolve())
    audio_dir = Path(abs_audio_path).parent
    file_name_with_ext = Path(abs_audio_path).name
    base_name = Path(abs_audio_path).stem

    if output_root_dir:
        output_root = Path(output_root_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        output_folder = output_root / base_name
    else:
        output_folder = audio_dir if audio_dir.name == base_name else audio_dir / base_name
    output_folder.mkdir(parents=True, exist_ok=True)

    return abs_audio_path, str(output_folder), base_name, file_name_with_ext


def run_pipeline(
    audio_file: str,
    model: str = "turbo",
    prompt: Optional[str] = DEFAULT_PROMPT,
    language: Optional[str] = "tl",
    hf_token: Optional[str] = None,
    clean_audio: bool = True,
    diarization: bool = True,
    move_original_file: bool = True,
    output_root_dir: Optional[str] = None,
    device: str = "cpu",
    verbose: bool = True,
    progress_callback: ProgressCallback = None,
):
    """Execute full transcription pipeline used by CLI and GUI."""

    def notify(message: str) -> None:
        _emit(message, callback=progress_callback, verbose=verbose)

    abs_audio_path, output_folder, base_name, file_name_with_ext = setup_output_folder(
        audio_file, output_root_dir=output_root_dir
    )
    save_prefix = os.path.join(output_folder, base_name)

    audio_source_for_transcription = abs_audio_path
    audio_source_for_diarization = None

    if clean_audio:
        notify("Cleaning audio with DeepFilterNet...")
        cleaned_wav = clean_audio_deepfilternet(abs_audio_path, output_folder)
        if cleaned_wav:
            audio_source_for_transcription = cleaned_wav
            audio_source_for_diarization = cleaned_wav
            notify("Audio cleaned successfully.")
        else:
            notify("Audio cleaning skipped or failed. Using original file.")

    notify("Loading Whisper model...")
    notify("Transcribing audio...")
    transcription_result = transcribe_audio(
        audio_source_for_transcription,
        model_size=model,
        prompt=prompt,
        language=language,
        device=device,
        verbose=verbose,
    )
    if not transcription_result:
        raise RuntimeError("Transcription failed.")
    notify("Transcription complete.")

    notify("Saving transcript outputs...")
    save_to_file(transcription_result["text"], transcription_result["segments"], save_prefix)

    final_segments = []
    should_diarize = diarization and bool(hf_token)

    if diarization and not hf_token:
        notify("Diarization enabled, but no Hugging Face token was provided. Skipping diarization.")

    if should_diarize:
        notify("Starting speaker diarization...")
        temp_wav_created = False

        if not audio_source_for_diarization:
            notify("Converting source audio to WAV for diarization...")
            audio_source_for_diarization = convert_to_wav(abs_audio_path)
            temp_wav_created = bool(audio_source_for_diarization)

        if audio_source_for_diarization:
            diarization_result = diarize_audio(
                audio_source_for_diarization,
                hf_token=hf_token,
                device=device,
                verbose=verbose,
            )
            if diarization_result:
                notify("Merging transcription with speaker segments...")
                final_segments = merge_transcription_and_diarization(
                    transcription_result["segments"], diarization_result
                )
                save_diarized_output(final_segments, save_prefix)
            else:
                notify("Diarization failed. Keeping plain transcription only.")

            if temp_wav_created and os.path.exists(audio_source_for_diarization):
                os.remove(audio_source_for_diarization)

    target_audio_path = os.path.join(output_folder, file_name_with_ext)
    if move_original_file and abs_audio_path != target_audio_path:
        notify("Moving original audio into the output folder...")
        try:
            shutil.move(abs_audio_path, target_audio_path)
        except Exception as exc:
            notify(f"Warning: Could not move original file: {exc}")

    notify("Pipeline complete.")

    return {
        "text": transcription_result["text"],
        "segments": final_segments if final_segments else transcription_result["segments"],
        "output_folder": output_folder,
        "save_prefix": save_prefix,
        "is_diarized": bool(final_segments),
        "source_audio": target_audio_path if move_original_file else abs_audio_path,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe Tagalog/English audio with Whisper and optional speaker diarization."
    )
    parser.add_argument("audio_file", help="Path to the audio file")
    parser.add_argument(
        "--model",
        default="turbo",
        help="Whisper model size (turbo, tiny, base, small, medium, large, large-v3)",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Initial prompt/context")
    parser.add_argument("--lang", default="tl", help="Language code (e.g. tl, en, auto)")
    parser.add_argument("--token", help="Hugging Face token for diarization", default="")
    parser.add_argument("--no-clean", action="store_true", help="Disable DeepFilterNet audio cleaning")
    parser.add_argument("--no-diarization", action="store_true", help="Disable speaker diarization")
    parser.add_argument("--device", default="cpu", help="Execution device: cpu, cuda, or mps")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output root directory. Results are saved in <output-dir>/<audio-file-name>/",
    )
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="Do not move the original audio file into the output folder",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Error: File not found: {args.audio_file}")
        return 1

    language = None if args.lang.lower() == "auto" else args.lang

    try:
        result = run_pipeline(
            audio_file=args.audio_file,
            model=args.model,
            prompt=args.prompt,
            language=language,
            hf_token=args.token,
            clean_audio=not args.no_clean,
            diarization=not args.no_diarization,
            move_original_file=not args.no_move,
            output_root_dir=args.output_dir or None,
            device=args.device,
            verbose=True,
            progress_callback=None,
        )
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    if result["is_diarized"]:
        print("\n--- Diarized Preview ---\n")
        for seg in result["segments"][:5]:
            print(f"[{seg['speaker']}]: {str(seg.get('text', '')).strip()}")
    else:
        print("\n--- Transcription Preview ---\n")
        text = result["text"]
        print(text[:500] + "..." if len(text) > 500 else text)

    print(f"\nSaved outputs in: {result['output_folder']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
