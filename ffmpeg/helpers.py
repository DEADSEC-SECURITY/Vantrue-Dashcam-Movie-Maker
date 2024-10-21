#  Copyright (c) 2022.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
from functools import lru_cache

# 3rd-Party Imports

# Local Imports


@lru_cache(maxsize=4)
def normalize_font_path(font_path: str) -> str:
    """
    Will normalize the font path.

    @font_path: str
    """

    font_path = font_path.replace("\\", "/").replace("C:", "C\\:")

    return font_path


def normalize_float(value: float) -> float:
    """
    Will normalize the float value.
    This is important cuz the more decimal values the more time
    ffmpeg takes to process the video.

    @value: float
    """

    return round(value, 4)


def fit_text_to_screen(text: str, max_letters: int) -> list:
    """
    Fit the text to the screen.
    """

    if len(text) <= max_letters:
        return [text]

    text_words = text.split(" ")
    lines: list = []
    current_phrase = ""

    for word in text_words:
        if len(current_phrase) + len(word) <= max_letters:
            if len(current_phrase) == 0:
                current_phrase = word
                continue
            current_phrase += f" {word}"
        else:
            lines.append(current_phrase)
            current_phrase = word

    if len(current_phrase) != 0:
        lines.append(current_phrase)

    return lines


def fix_ffmpeg_text(text: str) -> str:
    """
    Escapes chars that ffmpeg might interpret as commands
    """
    text = text.replace(":", r"\:")
    text = text.replace("'", r"")

    return text
