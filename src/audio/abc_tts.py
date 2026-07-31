from abc import ABC
from typing import Optional

import numpy as np
import librosa
from loguru import logger
import soundfile as sf

from src.schemas import Script, SpeechAdaptersList, CutAudio, CutInfo


def trim_edge_silence(
        input_path: str,
        output_path: str,
        top_db: int = 60,
        reduction_percentage: float = 1.0
) -> CutAudio:
    """Trims silence from the beginning and end of an audio file.

    This function loads an audio file, removes any leading or trailing silence,
    and saves the result to a new file.

    Args:
        input_path (str): The path to the input audio file.
        output_path (str): The path to save the output audio file.
        top_db (int, optional): The threshold in decibels below the peak
            amplitude to consider as silence. Defaults to 60.
        reduction_percentage (float, optional): The fraction of detected silence
            to remove, where 1.0 means remove all silence (trim) and 0.0
            means keep all silence. Must be between 0.0 and 1.0.
            Defaults to 1.0.

    Returns:
        CutAudio: An object containing details about the cuts made to the audio.
    """
    # Load the audio file, preserving its original sample rate
    y, sr = librosa.load(path=input_path, sr=None)
    original_length_samples = len(y)
    original_length_seconds = float(original_length_samples / sr)

    # Find the boundaries of the non-silent part of the audio
    _, index = librosa.effects.trim(y, top_db=top_db)
    start_index, end_index = index

    # Isolate the three main parts of the audio signal
    leading_silence = y[:start_index]
    content = y[start_index:end_index]
    trailing_silence = y[end_index:]

    # Calculate how many samples of silence to REMOVE from each end
    samples_to_remove_start = int(len(leading_silence) * reduction_percentage)
    samples_to_remove_end = int(len(trailing_silence) * reduction_percentage)

    # Create the new, shortened silent sections by slicing the original ones
    new_leading_silence = leading_silence[samples_to_remove_start:]

    # Handle the case where we remove 0 samples from the end
    if samples_to_remove_end > 0:
        new_trailing_silence = trailing_silence[:-samples_to_remove_end]
    else:
        new_trailing_silence = trailing_silence

    # Reconstruct the audio signal by concatenating the parts
    new_y = np.concatenate([new_leading_silence, content, new_trailing_silence])

    # Save the modified audio to the output file
    sf.write(file=output_path, data=new_y, samplerate=sr)

    # Calculate the duration of the removed audio in seconds for the return value
    start_trimmed_seconds = float(samples_to_remove_start / sr)
    end_trimmed_seconds = float(samples_to_remove_end / sr)

    return CutAudio(
        raw_filepath=input_path,
        cut_filepath=output_path,
        raw_audio_duration=original_length_seconds,
        cuts=[
            CutInfo(cut_time=0.0, cut_duration=start_trimmed_seconds),
            CutInfo(cut_time=(original_length_samples - len(trailing_silence)) / sr,
                    cut_duration=end_trimmed_seconds)
        ]
    )


def remove_all_silences(
        input_path: str,
        output_path: str,
        top_db: int = 60,
        reduction_percentage: float = 1.0,
) -> CutAudio:
    """
    Removes all silences from an audio file and returns a list of cuts.

    Args:
        input_path (str): Path to the input audio file.
        output_path (str): Path to save the output audio file.
        top_db (int): The threshold (in decibels) below the peak amplitude to
                      consider as silence. Defaults to 60.
        reduction_percentage (float): The fraction of detected silence to remove.
                                      1.0 removes all silence, 0.0 keeps all.
                                      Must be between 0.0 and 1.0. Defaults to 1.0.

    Returns:
        CutAudio: An object containing details about the cuts made to the audio.
    """
    logger.info(f"Loading audio file from: {input_path}")
    y, sr = librosa.load(path=input_path, sr=None)
    original_length = len(y)
    logger.info(f"Original audio length: {original_length / sr:.2f} seconds")

    non_silent_intervals = librosa.effects.split(y, top_db=top_db)

    if not non_silent_intervals.any():
        logger.warning("No non-silent intervals found. The audio might be entirely silent. Copying original file.")
        sf.write(file=output_path, data=y, samplerate=sr)
        return CutAudio(
            raw_filepath=input_path,
            cut_filepath=output_path,
            raw_audio_duration=original_length / sr,
            cuts=[]
        )

    new_audio_segments = []
    cuts_info = []
    last_end = 0

    for start, end in non_silent_intervals:
        # 1. Handle the silence before the current non-silent interval
        if start > last_end:
            silent_segment = y[last_end:start]
            samples_to_remove = int(len(silent_segment) * reduction_percentage)

            if samples_to_remove > 0:
                cut_time = last_end / sr
                cut_duration = samples_to_remove / sr
                cuts_info.append(CutInfo(cut_time=cut_time, cut_duration=cut_duration))

                # Keep the remaining part of the silence
                new_audio_segments.append(silent_segment[samples_to_remove:])

        # 2. Add the non-silent interval
        new_audio_segments.append(y[start:end])
        last_end = end

    # 3. Handle any trailing silence after the last non-silent interval
    if last_end < original_length:
        trailing_silence = y[last_end:]
        samples_to_remove = int(len(trailing_silence) * reduction_percentage)

        if samples_to_remove > 0:
            cut_time = last_end / sr
            cut_duration = samples_to_remove / sr
            cuts_info.append(CutInfo(cut_time=cut_time, cut_duration=cut_duration))

            # Keep the remaining part of the trailing silence
            new_audio_segments.append(trailing_silence[samples_to_remove:])

    # Reconstruct the audio
    new_y = np.concatenate(new_audio_segments)

    logger.info(f"Writing processed audio to: {output_path}")
    sf.write(file=output_path, data=new_y, samplerate=sr)

    total_removed_duration = sum(cut.cut_duration for cut in cuts_info)
    logger.info(f"Total silence removed: {total_removed_duration:.2f} seconds")

    return CutAudio(
        raw_filepath=input_path,
        cut_filepath=output_path,
        raw_audio_duration=original_length / sr,
        cuts=cuts_info
    )

class TTS(ABC):
    """
    Abstract base class for Text-to-Speech (TTS) systems.
    """

    def __init__(self):
        """Initialize the TTS system."""
        pass

    def generate_audio(self,
                       script: Script,
                       adapters: Optional[SpeechAdaptersList],
                       temp_folder: Optional[str],
                       splitted_texts_filepath: str,
                       enhanced_text_filepath: str,
                       cut_info_filepath: Optional[str],
                       filepath: Optional[str]
                       ) -> None:
        """Generate audio from script and save it to filepath.

        Args:
            script (Script): The script to convert to audio.
            adapters (SpeechAdaptersList, optional): List of speech adapters to modify the script. Defaults to None.
            temp_folder (str, optional): The temporary folder to save intermediate files. Defaults to None.
            enhanced_text_filepath (str): The path to save the enhanced text after applying Audio Tags.
            splitted_texts_filepath (str): The path to save the split of the text.
            cut_info_filepath (str, optional): The path to save the cut audio files information. Defaults to None.
            filepath (str, optional): The path of the file to save the audio to. Defaults to None.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def align(self,
              audio_filepath: str,
              temp_audio_folder: Optional[str],
              splitted_texts_filepath: str,
              cut_info_filepath: Optional[str],
              temp_alignment_folder: Optional[str],
              adapters: Optional[SpeechAdaptersList],
              alignment_filepath: Optional[str]
              ) -> None:
        """Align the script with the generated audio file.

        Args:
            adapters (SpeechAdaptersList, optional): List of speech adapters to modify the script. Defaults to None.
            temp_audio_folder (str, optional): The temporary folder containing intermediate audio files. Defaults to None.
            splitted_texts_filepath (str): The path to save the split of the text.
            cut_info_filepath (str, optional): The path to the cut audio files information. Defaults to None.
            temp_alignment_folder (str, optional): The temporary folder to save intermediate alignment files. Defaults to None.
            audio_filepath (str): The path of the audio file to align with the script.
            alignment_filepath (str, optional): The path to save the alignment data. Defaults to None.
        """
        raise NotImplementedError("Subclasses must implement this method.")
