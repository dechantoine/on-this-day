import json
import os

import click
import pandas as pd
from loguru import logger
from tqdm import tqdm

from app.utils import create_directory, load_chosen_script, load_image_prompts
from src.config import settings
from src.audio.elevenlabs_tts import ElevenLabsTTS
from src.video.moviepy_video import MoviepyVideo
from src.schemas import Events, QualifiedEvents, SpeechAdaptersList
from src.scripts.wiki import WikiEvents


@click.group()
def cli():
    pass

@click.command()
@click.option('--date', required=True, type=str, help='Date of the event in YYYY-MM-DD format.')
def build_from_app(date) -> None:
    """Build video from the chosen script and generated images."""
    logger.info(f"Building video from app data for date: {date}")

    year, month, day = map(int, date.split('-'))
    output_dir = create_directory(year, month, day)

    script = load_chosen_script(output_dir)
    image_prompts = load_image_prompts(output_dir)
    script_segments = [image.script_segment for image in image_prompts.image_prompts]
    #images_filepaths = [image.selected_image_path for image in image_prompts.image_prompts]

    el = ElevenLabsTTS()

    # Generate audio from the script
    enhanced_text_filepath = os.path.join(output_dir, settings.app.ENHANCED_TEXT_FILENAME)
    splitted_texts_filepath = os.path.join(output_dir, settings.app.SPLIT_TEXTS_FILENAME)
    audios_temp_folder = os.path.join(output_dir, settings.app.AUDIOS_TEMP_FOLDER)
    audio_filepath = os.path.join(output_dir, settings.app.AUDIO_FILENAME)
    cut_info_filepath = os.path.join(output_dir, settings.app.AUDIO_CUT_FILENAME)
    adapters_filepath = os.path.join(output_dir, settings.app.SPEECH_ADAPTERS_FILENAME)

    videos_filepaths = [os.path.join(output_dir, settings.app.ANIMATIONS_FOLDER, f"{i}.mp4")
                        for i in range(len(image_prompts.image_prompts))]

    if os.path.exists(adapters_filepath):
        with open(adapters_filepath, "r", encoding="utf-8") as f:
            adapters = SpeechAdaptersList.model_validate_json(f.read())
    else:
        adapters = None
        logger.info(f"No speech adapters file found at {adapters_filepath}, proceeding without adapters.")

    if not os.path.exists(audio_filepath):
        logger.info("Generating audio from the script...")
        el.generate_audio(script=script,
                          adapters=adapters,
                          temp_folder=audios_temp_folder,
                          enhanced_text_filepath=enhanced_text_filepath,
                          splitted_texts_filepath=splitted_texts_filepath,
                          cut_info_filepath=cut_info_filepath,
                          filepath=audio_filepath)
    else:
        logger.info(f"Audio file already exists at {audio_filepath}, skipping generation.")

    # Align audio with the script
    alignements_temp_folder = os.path.join(output_dir, settings.app.SPEECH_ALIGNMENT_TEMP_FOLDER)
    alignment_filepath = os.path.join(output_dir, settings.app.SPEECH_ALIGNMENT_FILENAME)
    if not os.path.exists(alignment_filepath):
        logger.info("Aligning audio with the script...")
        el.align(
            audio_filepath=audio_filepath,
            temp_audio_folder=audios_temp_folder,
            splitted_texts_filepath=splitted_texts_filepath,
            cut_info_filepath=cut_info_filepath,
            temp_alignment_folder=alignements_temp_folder,
            adapters=adapters,
            alignment_filepath=alignment_filepath
        )
    else:
        logger.info(f"Alignment file already exists at {alignment_filepath}, skipping alignment.")

    # Generate video from images and audio
    video_gen = MoviepyVideo()

    video_filepath = os.path.join(output_dir, settings.app.VIDEO_FILENAME)

    video_gen.build_video_from_videos(
         script_segments=script_segments,
         alignment_filepath=alignment_filepath,
         videos_filepaths=videos_filepaths,
         speech_path=audio_filepath,
         video_path=video_filepath,
         video_title=["Thriller:", "How One", "Album", "Changed", "Everything"]
    )

@click.command()
@click.option('--start-date', required=True, type=str, help='Date of the first day in YYYY-MM-DD format.')
@click.option('--end-date', required=True, type=str, help='Date of the last day in YYYY-MM-DD format.')
def fetch_events(start_date: str, end_date: str) -> None:
    """Fetch events from Wikipedia between start_date and end_date."""
    dates = pd.date_range(start=start_date, end=end_date)
    events_extractor = WikiEvents()
    for date in tqdm(dates, desc="Fetching events"):
        year, month, day = date.year, date.month, date.day
        output_dir = create_directory(year, month, day)
        file_path = os.path.join(output_dir, settings.app.WIKI_EVENTS_FILENAME)

        if os.path.exists(file_path):
            logger.info(f"Events file already exists for {date.strftime('%Y-%m-%d')} at {file_path}, loading...")
            with open(file_path, "r", encoding="utf-8") as f:
                events = Events.model_validate_json(f.read())
        else:
            events = events_extractor.get_events((month, day))

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(events.model_dump(mode='json'), f, indent=4)

        logger.info(f"Saved {len(events.events)} events for {date.strftime('%Y-%m-%d')} to {file_path}")

        file_path = os.path.join(output_dir, settings.app.WIKI_EVENTS_QUALIFIED_FILENAME)

        if os.path.exists(file_path):
            logger.info(f"Qualified events file already exists for {date.strftime('%Y-%m-%d')} at {file_path}, skipping qualification.")
            continue

        qualified_events = events_extractor.qualify_events(events)
        qualified_events = QualifiedEvents(qualified_events=qualified_events)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(qualified_events.model_dump(mode='json'), f, indent=4)

        logger.info(f"Saved {len(qualified_events.qualified_events)} qualified events for {date.strftime('%Y-%m-%d')} to {file_path}")

@click.command()
@click.option('--date', required=True, type=str, help='Date of the event in YYYY-MM-DD format.')
@click.option('--part-index', required=True, type=int, help='Index of the part to clean.')
def clean_audio_part(date: str, part_index: int) -> None:
    """Clean up temporary audio files for a specific date and part index."""
    year, month, day = map(int, date.split('-'))
    output_dir = create_directory(year, month, day)

    audio_filepath = os.path.join(output_dir, settings.app.AUDIO_FILENAME)
    alignement_filepath = os.path.join(output_dir, settings.app.SPEECH_ALIGNMENT_FILENAME)

    audios_temp_folder = os.path.join(output_dir, settings.app.AUDIOS_TEMP_FOLDER)
    alignments_temp_folder = os.path.join(output_dir, settings.app.SPEECH_ALIGNMENT_TEMP_FOLDER)

    temp_alignment_filepath = os.path.join(alignments_temp_folder, f"{part_index}.json")
    temp_audio_filepath = os.path.join(audios_temp_folder, f"{part_index}.mp3")

    if os.path.exists(temp_alignment_filepath):
        os.remove(temp_alignment_filepath)
        logger.info(f"Deleted temporary alignment file: {temp_alignment_filepath}")
    else:
        logger.warning(f"Temporary alignment file not found: {temp_alignment_filepath}")

    if os.path.exists(temp_audio_filepath):
        os.remove(temp_audio_filepath)
        logger.info(f"Deleted temporary audio file: {temp_audio_filepath}")
    else:
        logger.warning(f"Temporary audio file not found: {temp_audio_filepath}")

    if os.path.exists(audio_filepath):
        os.remove(audio_filepath)
        logger.info(f"Deleted main audio file: {audio_filepath}")
    else:
        logger.warning(f"Main audio file not found: {audio_filepath}")
    if os.path.exists(alignement_filepath):
        os.remove(alignement_filepath)
        logger.info(f"Deleted main alignment file: {alignement_filepath}")
    else:
        logger.warning(f"Main alignment file not found: {alignement_filepath}")



if __name__ == '__main__':
    cli.add_command(build_from_app)
    cli.add_command(fetch_events)
    cli.add_command(clean_audio_part)
    cli()
