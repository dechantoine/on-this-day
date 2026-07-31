from loguru import logger

from src.config import settings
from src.gemini import LLMGemini
from src.audio.prompts import audio_tags_prompt
from src.schemas import Script, EnhancedScript, SplittedSentences


class TextEnhancer:
    """
    A class to enhance text before text-to-speech conversion.
    """

    def __init__(self, temperature:int = 0.2):
        """Initialize the PromptsGenerator."""
        self.llm = LLMGemini(model_name=settings.gemini.GEMINI_TEXT_ENHANCER)
        self.temperature = temperature

    def add_audio_tags(self, script: Script) -> EnhancedScript:
        """Enhance text with audio tags for better TTS performance.

        Args:
            script (Script): The script to enhance.

        Returns:
            Script: The enhanced text with audio tags.
        """
        logger.info("Generating enhanced text with audio tags...")

        response = self.llm.generate_with_structured_output(
            prompt=audio_tags_prompt.format(script=str(script)),
            temperature=self.temperature,
            output_type=EnhancedScript,
        )

        return response

    def split_text(self, script: Script) -> SplittedSentences:
        """Splits a script into its five core components for audio generation.
        Each component (hook, context, rising_tension, climax, conclusion) will be
        treated as a separate sentence for TTS processing.

        Args:
            script (Script): The script to split.

        Returns:
            SplittedSentences: An object containing the list of script components.
        """
        return SplittedSentences(
            sentences=[
                script.hook,
                script.context,
                script.rising_tension,
                script.climax,
                script.conclusion
            ]
        )