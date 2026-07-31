import json
import re
import calendar
from typing import Optional

from loguru import logger
from moviepy import AudioFileClip, CompositeVideoClip, Clip, ImageClip, TextClip, VideoClip, VideoFileClip, concatenate_videoclips
from moviepy.video.fx import AccelDecel
import numpy as np
from PIL import Image

from src.config import settings
from src.schemas import TextsAlignedList, VideoAligned, ImageAligned, TextAligned, SplittedSentences
from src.video.pil_text import AdvancedTextWriter, TextWriterConfig, TextSegment

cutwords = ['AND', 'THAN', 'THEN', 'ON', 'FROM', 'TO', 'IN', 'WITH', 'OF', 'FOR', 'BETWEEN', 'BUT', 'BY']

def align_images_to_script(
    script_segments: list[str],
    texts_aligned: TextsAlignedList,
    images_filepaths: list[str],
) -> list[ImageAligned]:
    """Align images to the script based on the provided prompts and text timings.

    Args:
        script_segments (list[str]): The list of script segments corresponding to image prompts.
        texts_aligned (TextsAlignedList): The aligned texts with their timings.
        images_filepaths (list[str]): The list of image file paths.
    Returns:
        list[ImageAligned]: A list of ImageAligned objects containing the aligned images and their timings.
    """
    texts_aligned_copy = texts_aligned.texts.copy()

    image_alignement = []

    current_start_time = 0.0

    for i, segment in enumerate(script_segments):
        segment = segment.strip()
        for word in segment.split(' '):
            next_word = texts_aligned_copy.pop(0)
            next_word_text = next_word.text
            if next_word_text == ' ':
                next_word = texts_aligned_copy.pop(0)
                next_word_text = next_word.text
            if next_word_text == word:
                continue
            else:
                logger.error(f"Error while processing image prompt '{segment}': "
                    f"Image prompt '{word}' does not match word '{next_word_text}' in alignement.")

        image_alignement.append(ImageAligned(
            text = segment,
            path = images_filepaths[i],
            start_time = current_start_time,
            end_time = next_word.end_time,
            duration = round(next_word.end_time - current_start_time, 4)
        ))
        current_start_time = next_word.end_time

    return image_alignement


def clean_text(text: str) -> str:
    """Clean the given text for subtitles.
    Args:
        text (str): The text to clean.
    """
    text = (text
            .replace('"', "")
            .replace("'", "")
            .replace("*", "")
            .upper()
            )

    return text

def check_on_this_day(words: list[str]) -> bool:
    """Check if the phrase 'ON THIS DAY' is in the list of words.
    Args:
        words (list[str]): The list of words to check.
    """

    def is_castable_to_int(value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

    if words == [' ', 'ON', ' ', 'THIS', ' ', 'DAY,'] or words == ['ON', ' ', 'THIS', ' ', 'DAY,']:
        logger.debug('------ON THIS DAY found------')
        return True
    if (
            len(words) == 6
            and words[0]==' '
            and words[1] in [month.name for month in calendar.Month]
            and words[2] == ' '
            #and (is_castable_to_int(words[3][0])
            #    or is_castable_to_int(words[3][:2]))
            #and words[3][2:] == ','
            and words[4] == ' '
            and is_castable_to_int(words[5][:-1])
            and words[5][-1] == ','
    ):
        logger.debug('------DATE found------')
        return True


class MoviepyVideo:
    """Class for creating a video from images and audio using MoviePy."""

    def __init__(self) -> None:
        """Initialize the MoviepyVideo."""
        self.fps = settings.video.FPS
        self.image_height = settings.video.IMAGE_HEIGHT
        self.image_width = settings.video.IMAGE_WIDTH
        self.enable_zoom = settings.video.ENABLE_ZOOM
        self.zoom_start_scale = 1.0
        self.zoom_end_scale = settings.video.ZOOM_END_SCALE
        self.zoom_speed_scale = settings.video.ZOOM_SPEED_SCALE

        if self.enable_zoom and self.zoom_end_scale < 1.0:
            raise ValueError("Zoom effect must be at least 1.0")

        self.enable_subtitles = settings.video.subtitles.ENABLE
        self.subtitles_font = settings.video.subtitles.FONT
        self.subtitles_current_word_color = settings.video.subtitles.CURRENT_WORD_COLOR
        self.subtitles_other_words_color = settings.video.subtitles.OTHER_WORDS_COLOR
        self.subtitles_fontsize = settings.video.subtitles.FONTSIZE
        self.subtitles_position = settings.video.subtitles.POSITION
        self.subtitles_stroke_color = settings.video.subtitles.STROKE_COLOR
        self.subtitles_stroke_width = settings.video.subtitles.STROKE_WIDTH
        self.subtitles_bottom_margin = settings.video.subtitles.BOTTOM_MARGIN
        self.subtitles_left_margin = settings.video.subtitles.LEFT_MARGIN
        self.subtitles_right_margin = settings.video.subtitles.RIGHT_MARGIN
        self.subtitles_top_margin = settings.video.subtitles.TOP_MARGIN
        self.subtitles_line_spacing_ratio = settings.video.subtitles.LINE_SPACING_RATIO
        self.subtitles_max_characters = settings.video.subtitles.MAX_CHARACTERS

        self.enable_title = settings.video.title.ENABLE
        self.title_font = settings.video.title.FONT
        self.title_fontsize =settings.video.title.FONTSIZE
        self.title_text_color =settings.video.title.TEXT_COLOR
        self.title_position =settings.video.title.POSITION
        self.title_stroke_color = settings.video.title.STROKE_COLOR
        self.title_stroke_width =settings.video.title.STROKE_WIDTH
        self.title_line_spacing_ratio =settings.video.title.LINE_SPACING_RATIO
        self.title_max_characters =settings.video.title.MAX_CHARACTERS

        self.subtitles_config = None
        self.subtitles_generator = None

        if self.enable_subtitles:
            self.subtitles_config = TextWriterConfig(
                image_size=(self.image_width, self.image_height),
                font_path=self.subtitles_font,
                font_size=self.subtitles_fontsize,
                stroke_width=self.subtitles_stroke_width,
                stroke_color=self.subtitles_stroke_color,
                position=self.subtitles_position,
                margins={
                    "bottom": self.subtitles_bottom_margin,
                    "left": self.subtitles_left_margin,
                    "right": self.subtitles_right_margin,
                    "top": self.subtitles_top_margin
                },
                line_spacing_ratio=self.subtitles_line_spacing_ratio
            )

            self.subtitles_generator = AdvancedTextWriter(
                config=self.subtitles_config
            )

        self.title_config = None
        self.title_generator = None

        if self.enable_title:
            self.title_config = TextWriterConfig(
                image_size=(self.image_width, self.image_height),
                font_path=self.title_font,
                font_size=self.title_fontsize,
                stroke_width=self.title_stroke_width,
                stroke_color=self.title_stroke_color,
                position=self.title_position,
                line_spacing_ratio=self.subtitles_line_spacing_ratio
            )

            self.title_generator = AdvancedTextWriter(
                config=self.title_config
            )


    def zoom(self, clip: ImageClip) -> VideoClip:
        """Progressively zoom each frame of the clip to the given scale.

        Args:
            clip (ImageClip): The clip to zoom.

        Returns:
            ImageClip: The zoom.
        """
        original_width, original_height = clip.size

        def apply_centered_zoom_transform(get_frame, t):
            frame = get_frame(t)
            pil_image = Image.fromarray(frame)

            current_scale = self.zoom_start_scale + \
                            (self.zoom_end_scale - self.zoom_start_scale) * (t / clip.duration)

            scaled_w = original_width * (1 / current_scale)
            scaled_h = original_height * (1 / current_scale)

            box = (
                (original_width - scaled_w) / 2,
                (original_height - scaled_h) / 2,
                original_width - (original_width - scaled_w) / 2,
                original_height - (original_height - scaled_h) / 2
            )

            resized_image = pil_image.resize(
                size=(original_width, original_height),
                resample=Image.Resampling.LANCZOS,
                box=box
            )

            # Convert back to numpy array for MoviePy
            final_frame = np.array(resized_image)
            return final_frame

        return clip.transform(apply_centered_zoom_transform)

    def zoom_v2(self, clip: ImageClip) -> VideoClip:
        """Zoom each frame of the clip at the given speed.

        Args:
            clip (ImageClip): The clip to zoom.

        Returns:
            ImageClip: The zoom.
        """
        original_width, original_height = clip.size

        def apply_centered_zoom_transform(get_frame, t):
            frame = get_frame(t)
            pil_image = Image.fromarray(frame)

            current_scale = self.zoom_speed_scale ** t

            scaled_w = original_width * (1 / current_scale)
            scaled_h = original_height * (1 / current_scale)

            box = (
                (original_width - scaled_w) / 2,
                (original_height - scaled_h) / 2,
                original_width - (original_width - scaled_w) / 2,
                original_height - (original_height - scaled_h) / 2
            )

            resized_image = pil_image.resize(
                size=(original_width, original_height),
                resample=Image.Resampling.LANCZOS,
                box=box
            )

            # Convert back to numpy array for MoviePy
            final_frame = np.array(resized_image)
            return final_frame

        return clip.transform(apply_centered_zoom_transform)

    def build_image_clips(self,
                          images_aligned: list[ImageAligned],
                          ) -> list[ImageClip]:
        """Build a list of ImageClip objects containing the aligned images and their timings.

        Args:
            images_aligned (list[ImageAligned]): The aligned images to build.

        Returns:
            list[ImageClip]
        """
        image_clips = []

        for image_aligned in images_aligned:
            base_clip = ImageClip(image_aligned.path, duration=image_aligned.duration)

            if self.enable_zoom and base_clip.duration > 0:
                processed_clip = self.zoom_v2(clip=base_clip)
                image_clips.append(processed_clip)

            else:
                image_clips.append(base_clip)

        return image_clips

    def cut_sentences(self, words: list[str]) -> list[list[str]]:
        """Determine the next sentence to display.

        Args:
            words (list[str]): The list of words.

        Returns:
            list[list[str]]: The 2-lines next sentence.
        """
        sentence = []

        for i in range(len(words)):
            sentence.append(words[i])
            total_characters = sum([len(word) for word in sentence])

            if check_on_this_day(sentence):
                break

            if re.search(r"[.?!;]$", words[i]):
                break

            if (total_characters > 0.55 * self.subtitles_max_characters
                    and i + 1 < len(words)
                    and (words[i+1] in cutwords or re.search(r"[,;]$", words[i]))
            ):
                break
            if total_characters >= self.subtitles_max_characters:
                break

        # identify the middle character of the sentence
        cumsum_total_characters = np.cumsum([len(word) for word in sentence])
        breaking_index = np.where(cumsum_total_characters > cumsum_total_characters[-1]/2)[0][0]

        # decide to cut before or after the middle character
        cut_one = [sentence[:breaking_index],
                   sentence[breaking_index:]]

        cut_two = [sentence[:breaking_index + 1],
                   sentence[breaking_index + 1:]]

        # choose the cut that has the least difference in length between the two lines
        if (abs(sum(
                len(word) for word in cut_one[0]) - sum(len(word) for word in cut_one[1])
                ) <
              abs(sum(
                  len(word) for word in cut_two[0]) - sum(len(word) for word in cut_two[1]))
        ):
            return cut_one
        else:
            return cut_two

    def create_image_clip_from_lines(self,
                                     lines: list[list[str]],
                                     current_line_index: int,
                                     current_line_top: bool = True
                                     ) -> ImageClip:
        """Create an ImageClip from the given lines and highlight the current word.

        Args:
            lines (list[list[str]]): The 2 lines of text (top and bottom).
            current_line_index (int): The index of the current word to highlight.
            current_line_top (bool): Whether the current word is in the top line.

        Returns:
            ImageClip: The created ImageClip.
        """
        if current_line_top:
            if len(lines[0])>current_line_index:
                current_word = lines[0][current_line_index]
            else:
                current_word = ""
            contents = [
                [
                    TextSegment(text="".join(lines[0][:current_line_index]),
                                color=self.subtitles_other_words_color),
                    TextSegment(text=current_word,
                                color=self.subtitles_current_word_color
                                ),
                    TextSegment(text="".join(lines[0][current_line_index+1:]),
                                color=self.subtitles_other_words_color)
                ],
                [
                    TextSegment(text="".join(lines[1]), color=self.subtitles_other_words_color)
                ]
            ]
        else:
            if len(lines[1])>=current_line_index:
                current_word = lines[1][current_line_index]
            else:
                current_word=""
            contents = [
                [
                    TextSegment(text="".join(lines[0]), color=self.subtitles_other_words_color),
                ],
                [
                    TextSegment(text="".join(lines[1][:current_line_index]),
                                color=self.subtitles_other_words_color),
                    TextSegment(text=current_word,
                                color=self.subtitles_current_word_color),
                    TextSegment(text="".join(lines[1][current_line_index+1:]),
                                color=self.subtitles_other_words_color)
                ],
            ]

        image = self.subtitles_generator.create_advanced_text(lines=contents)
        image_clip = ImageClip(img=np.array(image))

        return image_clip

    def build_subtitles_clips(self,
                             texts_aligned: TextsAlignedList,
                             ) -> list[TextClip]:
        """Build a list of TextClip objects containing the aligned texts and their timings.

        Args:
            texts_aligned (list[TextAligned]): The aligned texts.

        Returns:
            list[TextClip]
        """
        subtitles_clips = []
        words = [clean_text(text=word.text) for word in texts_aligned.texts]
        words_ends = [0] + [word.end_time for word in texts_aligned.texts]

        while len(words) > 0:
            first_line, second_line = self.cut_sentences(
                words = words
            )

            # keep track of the length before any modification
            lines = [
                {
                    'line': line,
                    'raw_length': len(line),
                    'truncated_start': False,
                    'truncated_end': False
            } for line in [first_line, second_line]]

            for line in lines:
                if len(line['line']) == 0:
                    continue
                if line['line'][0] == ' ':
                    line['line'] = line['line'][1:]
                    line['truncated_start'] = True
                if line['line'] and line['line'][-1] == ' ':
                    line['line'] = line['line'][:-1]
                    line['truncated_end'] = True

            for i, line in enumerate(lines):
                if line['truncated_start']:
                    # repeat the first word of the line with the duration of the deleted space
                    image_clip = self.create_image_clip_from_lines(
                        lines=[l['line'] for l in lines],
                        current_line_index=0,
                        current_line_top=(i==0)
                    )
                    image_clip.start = words_ends[0]
                    image_clip.end = words_ends[1]
                    image_clip.duration = words_ends[1] - words_ends[0]
                    subtitles_clips.append(image_clip)
                    words_ends = words_ends[1:]

                len_line = len(line['line'])
                for k in range(len_line):
                    image_clip = self.create_image_clip_from_lines(
                        lines=[l['line'] for l in lines],
                        current_line_index=k,
                        current_line_top=(i==0)
                    )

                    image_clip.start = words_ends[k]
                    image_clip.end = words_ends[k + 1]
                    image_clip.duration = words_ends[k + 1] - words_ends[k]
                    subtitles_clips.append(image_clip)

                words_ends = words_ends[len_line:]

                if line['truncated_end']:
                    # repeat the last word of the line with the duration of the deleted space
                    image_clip = self.create_image_clip_from_lines(
                        lines=[l['line'] for l in lines],
                        current_line_index=len_line - 1,
                        current_line_top=(i==0)
                    )
                    image_clip.start = words_ends[0]
                    image_clip.end = words_ends[1]
                    image_clip.duration = words_ends[1] - words_ends[0]
                    subtitles_clips.append(image_clip)
                    words_ends = words_ends[1:]

                words = words[line['raw_length']:]

        subtitles_clips = concatenate_videoclips(clips=subtitles_clips,
                                                method="chain")

        return subtitles_clips

    def build_title_clip(self,
                         title: str,
                         image_filepath: str
                         ) -> VideoClip:
        """Build a list of TextClip objects containing the aligned texts and their timings.

        Args:
            title (str): the title of the video.

        Returns:
            VideoClip
        """
        base_clip = ImageClip(image_filepath)

        contents = [
            [
                TextSegment(text=word, color=self.title_text_color)
            ] for word in title.split(" ")
        ]

        image = self.title_generator.create_advanced_text(lines=contents)
        title_clip = ImageClip(img=np.array(image))

        title_clip = CompositeVideoClip(
            clips=[base_clip, title_clip],
            use_bgclip=True
        )

        title_clip.duration = 0.001

        return title_clip

    def build_video_from_images(
            self,
            script_segments: list[str],
            alignment_filepath: str,
            images_filepaths: list[str],
            speech_path: str,
            video_path: str,
            video_title: Optional[str],
        ) -> None:
        """Build the video from images and audio.

        Args:
            script_segments (list[str]): The list of script segments corresponding to image prompts.
            alignment_filepath (str): The path to the alignment data.
            images_filepaths (list[str]): The list of image file paths.
            speech_path (str): The path of the audio file.
            video_path (str): Where to save the video.
            video_title (Optional[str]): The title of the video.
        """
        with open(alignment_filepath, encoding='utf-8') as f:
            texts_aligned = TextsAlignedList.model_validate(json.load(f))

        script_segments = SplittedSentences.clean_audio_tags(script_segments)

        audio_clip = AudioFileClip(speech_path)

        # Ensure the last text segment ends at the end of the audio
        texts_aligned.texts[-1].end_time = audio_clip.duration

        images_aligned = align_images_to_script(
            script_segments = script_segments,
            texts_aligned = texts_aligned,
            images_filepaths = images_filepaths
        )

        images_clips = self.build_image_clips(
            images_aligned = images_aligned,
        )

        video_clip = concatenate_videoclips(images_clips, method="chain")

        if self.enable_subtitles:
            subtitles_clips = self.build_subtitles_clips(
                texts_aligned = texts_aligned,
            )

            video_clip = CompositeVideoClip(
                clips=[video_clip,subtitles_clips],
                use_bgclip=True
            )

        logger.debug(f"Video duration: {video_clip.duration} seconds")
        logger.debug(f"Audio duration: {audio_clip.duration} seconds")

        final_clip = video_clip.with_audio(audio_clip)

        if self.enable_title:
            title_clip = self.build_title_clip(
                title=video_title,
                image_filepath=images_filepaths[0]
            )

            final_clip = concatenate_videoclips([title_clip, final_clip], method="chain")

        final_clip.write_videofile(filename=video_path,
                                   fps=self.fps,
                                   codec='libx264',
                                   audio_codec='aac',
                                   preset='medium',
                                   threads=8)

    def resize_clip(self,
                    clip: Clip) -> Clip:
        """Resize and crop the clip to fit the target dimensions.

        Args:
            clip (Clip): The clip to resize.

        Returns:
            Clip: The resized and cropped clip.
        """
        if clip.size[0] < self.image_width:
            scale_factor = self.image_width / clip.size[0]
            new_height = int(clip.size[1] * scale_factor) + 1
            clip = clip.resized(height=new_height, width=self.image_width)

        if clip.size[1] < self.image_height:
            scale_factor = self.image_height / clip.size[1]
            new_width = int(clip.size[0] * scale_factor) + 1
            clip = clip.resized(height=self.image_height, width=new_width)

        if clip.size != (self.image_width, self.image_height):
            clip = clip.cropped(
                x_center=clip.w / 2,
                y_center=clip.h / 2,
                width=self.image_width,
                height=self.image_height
            )

        return clip

    def build_video_clips(self,
                          videos_aligned: list[VideoAligned],
                          ) -> list[VideoClip]:
        """Build a list of VideoClip objects from video files, adjusting duration.

        Clips are cut if speech is shorter or slowed down if speech is longer.

        Args:
            videos_aligned (list[ImageAligned]): The aligned videos to build,
                containing paths and target durations.

        Returns:
            list[VideoClip]: A list of processed VideoClip objects.
        """
        video_clips = []

        for video_aligned in videos_aligned:
            logger.debug(f"Processing video: {video_aligned.path}")

            # Ensure target duration is positive
            target_duration = video_aligned.duration
            base_clip = VideoFileClip(filename=video_aligned.path)

            logger.info(base_clip.size)

            processed_clip = base_clip.with_fps(fps=self.fps,
                                                change_duration=True)

            logger.info(processed_clip.size)

            original_duration = processed_clip.duration

            processed_clip = self.resize_clip(clip=processed_clip)

            if target_duration <= original_duration:
                # Speech is shorter: Cut the video clip
                logger.debug(f"Cutting video {video_aligned.path} from {original_duration:.2f}s "
                             f"to {target_duration:.2f}s")
                processed_clip = processed_clip.subclipped(
                    start_time=0,
                    end_time=target_duration
                )

            else:
                # Speech is longer: Slow the video down
                logger.debug(f"Slowing video {video_aligned.path} from {original_duration:.2f}s "
                             f"to {target_duration:.2f}s")

                processed_clip = AccelDecel(
                    abruptness=0,
                    soonness=1,
                    new_duration=target_duration
                ).apply(processed_clip)
                # Explicitly set duration to fix potential rounding issues
                processed_clip.duration = target_duration

                processed_clip = processed_clip.with_fps(fps=self.fps,
                                                         change_duration=False)

            logger.info(processed_clip.size)
            video_clips.append(processed_clip)

        return video_clips

    def build_title_clip_from_video(self,
                                    title: list[str],
                                    video_filepath: str
                                    ) -> VideoClip:
        """Build a title clip using the first frame of a video as the background.

        Args:
            title (list[str]): The title of the video.
            video_filepath (str): Path to the video file to use for the background.

        Returns:
            VideoClip: A very short video clip (0.001s) showing the title
                       over the first frame of the video.
        """
        video_first_frame = VideoFileClip(video_filepath).get_frame(0)
        base_clip = ImageClip(video_first_frame)

        base_clip = self.resize_clip(clip=base_clip)

        contents = [
            [
                TextSegment(text=words, color=self.title_text_color)
            ] for words in title
        ]

        image = self.title_generator.create_advanced_text(lines=contents)
        title_overlay_clip = ImageClip(img=np.array(image))
        title_overlay_clip.save_frame("debug_title_frame.png")

        title_video_clip = CompositeVideoClip(
            clips=[base_clip, title_overlay_clip],
            use_bgclip=True
        )

        title_video_clip.duration = 0.001
        return title_video_clip

    def build_video_from_videos(
            self,
            script_segments: list[str],
            alignment_filepath: str,
            videos_filepaths: list[str],
            speech_path: str,
            video_path: str,
            video_title: Optional[list[str]],
    ) -> None:
        """Build the video from video clips and audio.

        Args:
            script_segments (list[str]): The list of script segments.
            alignment_filepath (str): The path to the alignment data.
            videos_filepaths (list[str]): The list of video file paths.
            speech_path (str): The path of the audio file.
            video_path (str): Where to save the video.
            video_title (Optional[list[str]]): The title to overlay on the first frame.
        """
        with open(alignment_filepath, encoding='utf-8') as f:
            texts_aligned = TextsAlignedList.model_validate(json.load(f))

        script_segments = SplittedSentences.clean_audio_tags(script_segments)

        audio_clip = AudioFileClip(speech_path)

        # Ensure the last text segment ends at the end of the audio
        if texts_aligned.texts:
            texts_aligned.texts[-1].end_time = audio_clip.duration
        else:
            logger.error("No text alignment data found. Cannot proceed.")
            return

        # Align script segments (which correspond to videos) with timings
        videos_aligned = align_images_to_script(
            script_segments=script_segments,
            texts_aligned=texts_aligned,
            images_filepaths=videos_filepaths  # Use video paths here
        )

        # Build the list of processed video clips (cut or slowed)
        video_clips_list = self.build_video_clips(
            videos_aligned=videos_aligned,
        )

        # Concatenate all video clips into a single video track
        video_clip = concatenate_videoclips(video_clips_list, method="chain")

        # Add subtitles if enabled
        if self.enable_subtitles:
            subtitles_clips = self.build_subtitles_clips(
                texts_aligned=texts_aligned,
            )
            video_clip = CompositeVideoClip(
                clips=[video_clip, subtitles_clips],
                use_bgclip=True
            )

        logger.debug(f"Video duration: {video_clip.duration} seconds")
        logger.debug(f"Audio duration: {audio_clip.duration} seconds")

        # Set the final audio
        final_clip = video_clip.with_audio(audio_clip)

        # Add title card if enabled
        if self.enable_title and video_title:
            title_clip = self.build_title_clip_from_video(
                title=video_title,
                video_filepath=videos_filepaths[0]
            )
            final_clip = concatenate_videoclips([title_clip, final_clip], method="chain")

        final_clip.write_videofile(filename=video_path,
                                   fps=self.fps,
                                   codec='libx264',
                                   audio_codec='aac',
                                   preset='medium',
                                   threads=8)
        logger.info(f"Successfully created video: {video_path}")