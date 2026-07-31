from typing import Optional
import os

from elevenlabs import save
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings

from loguru import logger
import numpy as np
from pydub import AudioSegment
from tqdm import tqdm

from src.audio.abc_tts import TTS, trim_edge_silence, remove_all_silences
from src.audio.text_enhancer import TextEnhancer
from src.config import settings
from src.schemas import TextsAlignedList, TextAligned, SpeechAdaptersList, CutAudio, CutAudioList, SplittedSentences
from src.scripts.scripts import Script, script_to_string

def find_sublist_indices(sublst: list[str], lst: list[str]) -> list[tuple[int, int]]:
    """Find the start and end indices of a sublist within a list.

    Args:
        sublst (list[str]): The sublist to find.
        lst (list[str]): The list to search within.

    Returns:
        list[tuple[int, int]]: A list of tuples containing the start and end indices of each occurrence of the sublist.
    """
    sublen = len(sublst)
    indices = []
    for i in range(len(lst) - sublen + 1):
        if lst[i:i + sublen] == sublst:
            indices.append((i, i + sublen - 1))
    return indices


class ElevenLabsTTS(TTS):
    """
    A class for ElevenLabs Text-to-Speech (TTS) system.
    """

    def __init__(self):
        """Initialize the ElevenLabs TTS system."""
        super().__init__()
        self.client = ElevenLabs(
            api_key=settings.eleven_labs.API_KEY,
        )
        self.text_enhancer = TextEnhancer()
        self.voice_id = settings.eleven_labs.VOICE_ID
        self.model_id = settings.eleven_labs.MODEL_ID
        self.output_format = settings.eleven_labs.OUTPUT_FORMAT
        self.apply_text_normalization = settings.eleven_labs.voice_settings.APPLY_TEXT_NORMALIZATION
        self.stability = settings.eleven_labs.voice_settings.STABILITY
        self.use_speaker_boost = settings.eleven_labs.voice_settings.USE_SPEAKER_BOOST
        self.similarity_boost = settings.eleven_labs.voice_settings.SIMILARITY_BOOST
        self.style = settings.eleven_labs.voice_settings.STYLE
        self.speed = settings.eleven_labs.voice_settings.SPEED

        self.trim_only = settings.audio.TRIM_ONLY
        self.silence_top_db = settings.audio.SILENCE_TOP_DB
        self.silence_percentage = settings.audio.SILENCE_REDUCTION_PERCENTAGE

    @classmethod
    def credits_estimates(cls, script: Script) -> int:
        """Estimate the number of credits required for the given script.

        Args:
            script (Script): The script to estimate credits for.

        Returns:
            int: The estimated number of credits.
        """
        text = script_to_string(script)
        return len(text)

    def generate_raw_audio(self,
                           preceding_text: Optional[str],
                           current_text: str,
                           following_text: Optional[str],
                           filepath: str = None
                           ) -> None:
        """Generate audio from text and save it to filepath.

        Args:
            preceding_text (str, optional): The text preceding the current text. Defaults to None.
            current_text (str): The current text to be converted to audio.
            following_text (str, optional): The text following the current text. Defaults to None.
            filepath (str, optional): The path of the file to save the audio to. Defaults to None.
        """
        audio = self.client.text_to_speech.convert(
            text=current_text,
            #previous_text=preceding_text, # not yet supported by eleven_v3
            #next_text=following_text, # not yet supported by eleven_v3
            voice_id=self.voice_id,
            model_id=self.model_id,
            output_format=self.output_format,
            apply_text_normalization=self.apply_text_normalization,
            language_code=None,
            voice_settings=VoiceSettings(
                stability=self.stability,
                use_speaker_boost=self.use_speaker_boost,
                similarity_boost=self.similarity_boost,
                style=self.style,
                speed=self.speed
            )
        )

        save(audio=audio,
             filename=filepath)

    def generate_audio(self,
                       script: Script,
                       adapters: Optional[SpeechAdaptersList],
                       temp_folder: str,
                       enhanced_text_filepath: str,
                       splitted_texts_filepath: str,
                       cut_info_filepath: Optional[str],
                       filepath: Optional[str]
                       ) -> None:
        """Generate audio from script and save it to filepath.

        Args:
            script (Script): The script to convert to audio.
            adapters (SpeechAdaptersList, optional): List of speech adapters to modify the script. Defaults to None.
            temp_folder (str): The temporary folder to save intermediate files.
            enhanced_text_filepath (str): The path to save the enhanced text after applying Audio Tags.
            splitted_texts_filepath (str): The path to save the split of the text.
            cut_info_filepath (str, optional): The path to save the cut audio files information. Defaults to None.
            filepath (str, optional): The path of the file to save the audio to. Defaults to None.
        """
        if filepath is None:
            filepath = f"{script.id}.mp3"

        os.makedirs(temp_folder, exist_ok=True)

        if not os.path.exists(enhanced_text_filepath):
            enhanced_text = self.text_enhancer.add_audio_tags(script)
            with open(enhanced_text_filepath, 'w', encoding='utf-8') as f:
                f.write(enhanced_text.model_dump_json(indent=4))
        else:
            logger.info(f"Enhanced text file already exists at {enhanced_text_filepath}, loading.")
            with open(enhanced_text_filepath, 'r', encoding='utf-8') as f:
                enhanced_text = Script.model_validate_json(f.read())

        if not os.path.exists(splitted_texts_filepath):
            splitted_texts = self.text_enhancer.split_text(script=enhanced_text)

            with open(splitted_texts_filepath, 'w', encoding='utf-8') as f:
                f.write(splitted_texts.model_dump_json(indent=4))

        else:
            logger.info(f"Split text file already exists at {splitted_texts_filepath}, loading.")
            with open(splitted_texts_filepath, 'r', encoding='utf-8') as f:
                splitted_texts = SplittedSentences.model_validate_json(f.read())

        if adapters:
            for adapter in adapters.adapters:
                splitted_texts.sentences = [
                    sentence.replace(adapter.original_text, adapter.adapted_text)
                    for sentence in splitted_texts.sentences
                ]

        sentences = splitted_texts.sentences

        for i in tqdm(range(len(sentences)), desc="Generating audio segments"):
            temp_filepath = os.path.join(temp_folder, f"{i}.mp3")
            if not os.path.exists(temp_filepath):
                self.generate_raw_audio(
                    preceding_text=sentences[i - 1] if i > 0 else None,
                    current_text=sentences[i],
                    following_text=sentences[i + 1] if i < len(sentences) - 1 else None,
                    filepath=temp_filepath
                )
            else:
                logger.info(f"Audio file already exists at {temp_filepath}, skipping generation.")

        cuts_info = CutAudioList(
            audios=[]
        )
        if self.trim_only:
            # trim the edge silence
            for i in range(len(sentences)):
                input_filepath = os.path.join(temp_folder, f"{i}.mp3")
                output_filepath = os.path.join(temp_folder, f"{i}_cut.mp3")
                cut_info = trim_edge_silence(
                    input_path=input_filepath,
                    output_path=output_filepath,
                    top_db=self.silence_top_db,
                    reduction_percentage=self.silence_percentage
                )
                cuts_info.audios.append(
                    cut_info
                )
        else:
            # trim the edge silence and reduce the silence in between
            for i in range(len(sentences)):
                input_filepath = os.path.join(temp_folder, f"{i}.mp3")
                output_filepath = os.path.join(temp_folder, f"{i}_cut.mp3")
                cut_info = remove_all_silences(
                    input_path=input_filepath,
                    output_path=output_filepath,
                    top_db=self.silence_top_db,
                    reduction_percentage=self.silence_percentage,
                )
                cuts_info.audios.append(
                    cut_info
                )

        # concatenate all the cut audio files in the temp_folder
        combined = AudioSegment.empty()
        for i in range(len(sentences)):
            sound = AudioSegment.from_mp3(os.path.join(temp_folder, f"{i}_cut.mp3"))
            combined += sound
        combined.export(filepath, format="mp3")

        # save the cut audio files information
        with open(cut_info_filepath, 'w') as f:
            f.write(cuts_info.model_dump_json(indent=4))

        # delete all the cut temp audio files
        for i in range(len(sentences)):
            os.remove(os.path.join(temp_folder, f"{i}_cut.mp3"))


    def align_raw(self,
                  text: str,
                  audio_filepath: str,
                  alignment_filepath: str,
                  adapters: Optional[SpeechAdaptersList],
                  ) -> None:
        """Align the text with the generated audio file.

        Args:
            text (str): The text to be aligned with the audio.
            adapters (SpeechAdaptersList, optional): List of speech adapters to modify the text. Defaults to None.
            audio_filepath (str): The path of the audio file to align with the text.
            alignment_filepath (str): The path to save the alignment data.
        """
        if adapters:
            for adapter in adapters.adapters:
                text = text.replace(adapter.original_text, adapter.adapted_text)

        with open(audio_filepath, 'rb') as fd:
            audio_data = fd.read()

        transcription = self.client.forced_alignment.create(
            file=audio_data,
            text=text
        )

        alignment = TextsAlignedList(
            texts=[TextAligned(
                text=word.text,
                start_time=word.start,
                end_time=word.end
            ) for word in transcription.words]
        )

        if adapters:
            for adapter in adapters.adapters:

                adapted_list = adapter.adapted_text.split()
                # add spaces between each word
                new_size = len(adapted_list) * 2 - 1
                interspersed = [' '] * new_size
                interspersed[0::2] = adapted_list
                adapted_list = interspersed

                original_list = adapter.original_text.split()
                # add spaces between each word
                new_size = len(original_list) * 2 - 1
                interspersed = [' '] * new_size
                interspersed[0::2] = original_list
                original_list = interspersed

                sublist_indices = find_sublist_indices(
                    sublst=adapted_list,
                    lst=[t.text for t in alignment.texts]
                )

                # reverse the sublist_index to go from last to first to prevent index shifting
                for sublist_index in sublist_indices[::-1]:
                    start_time = alignment.texts[sublist_index[0]].start_time
                    end_time = alignment.texts[sublist_index[1]].end_time

                    start_times = list(np.arange(
                        start_time,
                        end_time,
                        (end_time - start_time) / len(original_list)
                    ))
                    end_times = start_times[1:] + [end_time]

                    del alignment.texts[sublist_index[0]:sublist_index[1] + 1]

                    for i, word in enumerate(original_list):
                        alignment.texts.insert(
                            sublist_index[0] + i,
                            TextAligned(
                                text=word,
                                start_time=start_times[i],
                                end_time=end_times[i]
                            )
                        )

        with open(alignment_filepath, 'w', encoding='utf-8') as f:
            f.write(alignment.model_dump_json(indent=4))

    def align(self,
              audio_filepath: str,
              temp_audio_folder: str,
              cut_info_filepath: Optional[str],
              splitted_texts_filepath: str,
              temp_alignment_folder: str,
              adapters: Optional[SpeechAdaptersList],
              alignment_filepath: Optional[str]
              ) -> None:
        """Align the script with the generated audio file.

        Args:
            audio_filepath (str): The path of the audio file to align with the script.
            temp_audio_folder: The temporary folder containing intermediate audio files.
            splitted_texts_filepath (str): The path to save the split of the text.
            cut_info_filepath (str, optional): The path to the cut audio files information. Defaults to None.
            temp_alignment_folder: The temporary folder to save intermediate alignment files.
            adapters (SpeechAdaptersList): List of speech adapters to modify the script.
            alignment_filepath (str, optional): The path to save the alignment data. Defaults to None.
        """
        with open(splitted_texts_filepath, 'r', encoding='utf-8') as f:
            splitted_texts = SplittedSentences.model_validate_json(f.read())

        splitted_texts.sentences = SplittedSentences.clean_audio_tags(splitted_texts.sentences)

        os.makedirs(temp_alignment_folder, exist_ok=True)

        sentences = splitted_texts.sentences
        for i in tqdm(range(len(sentences)), desc="Aligning segments"):
            temp_alignment_filepath = os.path.join(temp_alignment_folder, f"{i}.json")
            temp_audio_filepath = os.path.join(temp_audio_folder, f"{i}.mp3")
            if not os.path.exists(temp_alignment_filepath):
                self.align_raw(text=sentences[i],
                               adapters=adapters,
                               audio_filepath=temp_audio_filepath,
                               alignment_filepath=temp_alignment_filepath
                               )
            else:
                logger.info(f"Alignment file already exists at {temp_alignment_filepath}, skipping alignment.")

        # Build the final alignment file by combining individual segment alignments
        final_alignment = TextsAlignedList(texts=[])

        with open(cut_info_filepath, 'r', encoding='utf-8') as f:
            cuts_info_list = CutAudioList.model_validate_json(f.read())

        offset = 0.0  # The running duration of the final concatenated audio
        for i in tqdm(range(len(sentences)), desc="Combining alignment segments"):
            # Get the cut info for the current audio segment
            segment_cut_info = cuts_info_list.audios[i]
            cuts_in_segment = segment_cut_info.cuts

            # Load the alignment data for the original (uncut) segment
            temp_alignment_filepath = os.path.join(temp_alignment_folder, f"{i}.json")
            with open(temp_alignment_filepath, 'r', encoding='utf-8') as f:
                temp_alignment = TextsAlignedList.model_validate_json(f.read())

            # Set first word start time to 0 and last word end time to segment duration
            if len(temp_alignment.texts) > 0:
                temp_alignment.texts[0].start_time = 0.0
                temp_alignment.texts[-1].end_time = segment_cut_info.raw_audio_duration

            # Adjust timestamps for each word based on the cuts made before it
            for word in temp_alignment.texts:
                # Calculate total silence removed before the word started in its segment
                previous_cuts = [
                    cut for cut in cuts_in_segment
                    if cut.cut_time + cut.cut_duration <= word.start_time
                ]
                previous_time_shift = sum(
                    cut.cut_duration for cut in previous_cuts
                )

                # Calculate the silence overlapping with the end of previous word and the start of the current word
                start_cuts = [
                    cut for cut in cuts_in_segment
                    if cut.cut_time < word.start_time < cut.cut_time + cut.cut_duration < word.end_time]
                start_time_shift = sum(
                    word.start_time - cut.cut_time
                    for cut in start_cuts
                )

                # Calculate the silence removed during the word
                fully_cuts = [
                    cut for cut in cuts_in_segment
                    if word.start_time <= cut.cut_time + cut.cut_duration <= word.end_time]
                fully_within_shift = sum(
                    cut.cut_duration
                    for cut in fully_cuts
                )

                # Calculate the silence removed that overlaps with the end of the word
                end_cuts = [
                    cut for cut in cuts_in_segment
                    if (word.start_time < cut.cut_time < word.end_time < cut.cut_time + cut.cut_duration)
                ]
                end_time_shift = sum(
                    word.end_time - cut.cut_time
                    for cut in end_cuts
                )

                # Calculate the new start/end times relative to the cut segment's start
                new_start_time = word.start_time + offset - previous_time_shift - start_time_shift
                new_end_time = word.end_time + offset - previous_time_shift - fully_within_shift - end_time_shift

                # Append the word
                final_alignment.texts.append(
                    TextAligned(
                        text=word.text,
                        start_time=new_start_time ,
                        end_time=new_end_time
                    )
                )

            # Update the global offset by adding the duration of the current *cut* segment
            total_removed_duration = sum(cut.cut_duration for cut in cuts_in_segment)
            cut_segment_duration = (
                    segment_cut_info.raw_audio_duration - total_removed_duration
            )
            offset += cut_segment_duration

        with open(alignment_filepath, 'w', encoding='utf-8') as f:
            f.write(final_alignment.model_dump_json(indent=4))
        logger.info(f"Final combined alignment saved to {alignment_filepath}")
