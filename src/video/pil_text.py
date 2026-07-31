from typing import List, Literal

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field


class TextSegment(BaseModel):
    """Represents a single segment of text with a specific color."""
    text: str = Field(..., description="The text content of the segment.")
    color: str = Field(..., description="The color of the text (e.g., 'white', '#FFFF00').")


class TextWriterConfig(BaseModel):
    """Configuration for text writing."""
    image_size: tuple[int, int] = Field((1920, 1080), description="Size of the video frame (width, height).")
    font_path: str = Field(..., description="Path to the .ttf font file.")
    font_size: float = Field(60., gt=0, description="Font size in points.")
    stroke_width: float = Field(2., description="Width of the text outline/stroke.")
    stroke_color: str | None = Field("black", description="Color of the text outline/stroke.")
    position: Literal[
        "bottom_center", "top_center", "center",
        "bottom_left", "bottom_right", "top_left", "top_right"
    ] = Field("bottom_center", description="Position of the text block on the frame.")
    margins: dict[str, int] = Field({
        "top": 50, "bottom": 50, "left": 50, "right": 50
    }, description="Margins for the text from the edge of the frame.")
    line_spacing_ratio: float = Field(1.2, description="Multiplier for line height based on font size.")


class AdvancedTextWriter:
    """Advanced text writing."""

    def __init__(self, config: TextWriterConfig):
        self.config = config
        self.font = ImageFont.truetype(
            font=self.config.font_path,
            size=self.config.font_size
        )

    def create_advanced_text(
            self,
            lines: List[List[TextSegment]],
    ) -> Image.Image:
        """
        Generates a text image with advanced styling and positioning.

        Args:
            lines: A list of lines, where each line is a list of TextSegments.

        Returns:
            A Pillow Image object with the rendered text on a transparent background.
        """
        # Create an RGBA image for transparency
        image = Image.new("RGBA", self.config.image_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # --- 1. Measure the entire text block ---
        line_widths = [
            sum(self.font.getlength(seg.text) for seg in line)
            for line in lines
        ]
        max_text_width = max(line_widths) if line_widths else 0
        line_height = self.config.font_size * self.config.line_spacing_ratio
        total_text_height = line_height * len(lines)

        # --- 2. Calculate top-left starting position of the text block ---
        # Horizontal alignment
        if "left" in self.config.position:
            block_x = self.config.margins["left"]
        elif "right" in self.config.position:
            block_x = self.config.image_size[0] - max_text_width - self.config.margins["right"]
        else:  # center
            block_x = (self.config.image_size[0] - max_text_width) / 2

        # Vertical alignment
        if "top" in self.config.position:
            block_y = self.config.margins["top"]
        elif "bottom" in self.config.position:
            block_y = self.config.image_size[1] - total_text_height - self.config.margins["bottom"]
        else:  # center
            block_y = (self.config.image_size[1] - total_text_height) / 2

        # --- 3. Draw each line and segment ---
        current_y = block_y
        for i, line in enumerate(lines):
            # Handle text alignment within the block
            line_width = line_widths[i]
            if "left" in self.config.position:
                current_x = block_x
            elif "right" in self.config.position:
                current_x = block_x + (max_text_width - line_width)
            else:  # center
                current_x = block_x + (max_text_width - line_width) / 2

            for segment in line:
                draw.text(
                    (current_x, current_y),
                    segment.text,
                    fill=segment.color,
                    font=self.font,
                    stroke_width=self.config.stroke_width,
                    stroke_fill=self.config.stroke_color,
                )
                current_x += self.font.getlength(segment.text)

            current_y += line_height

        return image
