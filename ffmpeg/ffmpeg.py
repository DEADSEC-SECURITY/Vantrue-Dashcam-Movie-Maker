#  Copyright (c) 2022.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
from __future__ import annotations

import re
import subprocess
import sys
import warnings
import logging
from datetime import datetime
from typing import List, Tuple, Optional

# 3rd-Party Imports

# Local Imports
from .helpers import normalize_float, normalize_font_path, fix_ffmpeg_text
from .types import Input, Output, Dimension, Position, Seconds, Volume


def get_logger(name, level=logging.DEBUG):
    """
    This function will initialize a logger object

    :return: logger instance
    """

    logger = logging.getLogger(name)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s::%(name)s::%(levelname)s::%(message)s")
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(console_handler)

    return logger


logger = get_logger("FFMPEG")


class RoundFloats:
    def __init__(self, n_decimals: int = 2):
        self._n_decimals = n_decimals

    def __call__(self, function):
        def wrapper(cls, *args, **kwargs):
            return_args = []
            for arg in args:
                if isinstance(arg, float):
                    arg = round(arg, self._n_decimals)
                return_args.append(arg)

            return_kargs = {}
            for key, arg in kwargs.items():
                if isinstance(arg, float):
                    arg = round(arg, self._n_decimals)
                return_kargs[key] = arg

            return function(cls, *return_args, **return_kargs)

        return wrapper


class FFMPEG:
    """
    Interact with FFMPEG using python.
    """

    _silent_audio_streams = (
        {}
    )  # Saves the silent audio streams for each duration, so it can be reused

    def __init__(self, ffmpeg_path: str = "ffmpeg", use_gpu=False):
        self.ffmpeg_path = ffmpeg_path

        self._debug = True

        # Set default values
        self._set_defaults()

        self.extra_input_options = []
        if use_gpu:
            self.extra_input_options.extend(
                ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
            )

    def __str__(self) -> str:
        """
        Return the ffmpeg path.
        """

        if self._output_added:
            cmd = " ".join(self.cmd)

            filters = self._compile_filter_complex()
            filters = filters if filters else None

            settings = " ".join(self._compile_settings())

            return (
                f"Base Command: {cmd}\nSettings: {settings}\nFilter Complex: {filters}"
            )

        return f"Full Command: {self.cmd}"

    def _set_defaults(self) -> None:
        """
        Set default values.
        """

        self.cmd = [self.ffmpeg_path]
        self.filter_complex = []
        self.maps = []

        self._quality = "20"  # The lower, the better quality
        self._preset = "slow"
        self._pix_format = None
        self._video_encoder = "h264_nvenc"
        self._audio_encoder = "aac"
        self._bitrate = "44100"
        self._output_added = False
        self._overwrite_output = True
        self._input_count = 0

    def _compile_settings(self) -> List[str]:

        settings: list = []

        if self._video_encoder:
            settings.extend(["-c:v", self._video_encoder])

        if self._audio_encoder:
            settings.extend(["-c:a", self._audio_encoder])

        if self._bitrate:
            settings.extend(["-b:a", self._bitrate])

        if self._quality:
            settings.extend(["-qp", self._quality])

        if self._preset:
            settings.extend(["-preset", self._preset])

        if self._pix_format:
            settings.extend(["-pix_fmt", self._pix_format])

        if self._overwrite_output:
            settings.extend(["-y"])

        return settings

    def _add_settings(self) -> FFMPEG:
        """
        Add the settings to the command.
        """

        self.cmd.extend(self._compile_settings())
        return self

    def _compile_filter_complex(self) -> str:
        """
        Compile the filter complex.
        """

        commands = "".join(self.filter_complex)
        if commands.endswith(";"):
            commands = commands[:-1]

        return commands

    def _add_filter_complex(self) -> FFMPEG:
        """
        Add the filter complex to the command.
        """

        if self.filter_complex:
            commands = self._compile_filter_complex()
            self.cmd.extend(["-filter_complex", commands])
            self.cmd.extend(self.maps)
        return self

    @property
    def debug(self) -> bool:
        """
        Set the _debug mode.
        """
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        self._debug = value

    @property
    def quality(self) -> str:
        """
        Get the quality.
        """

        return self._quality

    @quality.setter
    def quality(self, value: str) -> None:
        """
        Set the quality.
        """

        self._quality = value

    @property
    def audio_encoder(self) -> str:
        """
        Get the encoder.
        """

        return self._audio_encoder

    @audio_encoder.setter
    def audio_encoder(self, value: str) -> None:
        """
        Set the encoder.
        """

        self._audio_encoder = value

    @property
    def bitrate(self) -> str:
        """
        Get the bitrate.
        """

        return self._bitrate

    @bitrate.setter
    def bitrate(self, value: str) -> None:
        """
        Set the bitrate.
        """

        if value != 44100:
            warnings.warn(
                "Setting a bitrate different than 44100 might not work is certain devices."
            )

        self._bitrate = value

    @property
    def overwrite_output(self) -> bool:
        """
        Get the overwrite output.
        """

        return self._overwrite_output

    @overwrite_output.setter
    def overwrite_output(self, value: bool) -> None:
        """
        Set to overwrite output.
        """

        self._overwrite_output = value

    @property
    def input_count(self) -> int:
        """
        Get the input count.
        """

        return self._input_count

    @property
    def current_input_index(self) -> int:
        """
        Get the current input index.

        Normally called after adding an input to get the index of the recently added input,
        usefully when inputs are dynamically added.
        """

        return self._input_count - 1

    def reset(self) -> FFMPEG:
        """
        Reset the class to default values.
        Useful when you want to run different commands under the same instance.
        """

        self._set_defaults()

        return self

    @RoundFloats()
    def add_input(self, input_file: str, start_from: Optional[float] = None) -> FFMPEG:
        """
        Add an input file.

        @param input_file: The input file.
        @param start_from: Will make the video start from this time in seconds.
        """

        input_cmd = self.extra_input_options.copy()
        if start_from:
            # There are some error as expected from cutting and also recording so to try to avoid it
            # we just add a couple milliseconds to the start time.
            start_from += 0.250
            start_from = datetime.utcfromtimestamp(start_from).strftime("%H:%M:%S.%f")[
                :-3
            ]
            input_cmd.extend(["-ss", start_from, "-i", input_file])
        else:
            input_cmd.extend(["-i", input_file])

        self.cmd.extend(input_cmd)
        self._input_count += 1
        return self

    def add_output(self, output_file: str) -> FFMPEG:
        """
        Add an output file.
        """

        self._add_settings()
        self._add_filter_complex()

        self.cmd.extend([output_file])
        self._output_added = True
        return self

    def add_time_limit(self, time_limit: str) -> FFMPEG:
        """
        Will add a time limit to the video.
        """

        self.cmd.extend(["-t", str(time_limit)])
        return self

    """
        SINGLE RUN COMMANDS
    """

    def get_media_duration(self) -> float:
        """
        Get the media duration of the input file.
        """

        process = subprocess.Popen(self.cmd, stderr=subprocess.PIPE)
        process.wait()
        output = process.stderr.read().decode("utf-8")
        process.stderr.close()

        logger.debug(f"Output from 'get_media_duration': {output}")

        pattern = r"Duration: (\d{2}):(\d{2}):(\d{2}.\d{2})"
        matches = re.search(pattern, output).groups()

        hours = float(matches[0])
        minutes = float(matches[1])
        seconds = float(matches[2])

        return normalize_float((hours * 60) * 60 + minutes * 60 + seconds)

    def get_media_width_height(self) -> Tuple[int, int]:
        """
        Get the media duration of the input file.
        """

        process = subprocess.Popen(self.cmd, stderr=subprocess.PIPE)
        process.wait()
        output = process.stderr.read().decode("utf-8")
        process.stderr.close()

        logger.debug(f"Output from 'get_media_width_height': {output}")

        pattern = r"Video:.*, (\d{3,5})x(\d{3,5})"
        matches = re.search(pattern, output).groups()

        height = int(matches[1])
        width = int(matches[0])

        return width, height

    """
        FILTERS COMMANDS
    """

    def add_filter_complex(self, filter_complex: str) -> FFMPEG:
        """
        Add a custom filter complex.
        """

        self.filter_complex.append(filter_complex)
        return self

    @RoundFloats()
    def pad_equally(
        self,
        input: Input,
        width: Dimension,
        height: Dimension,
        color: str,
        output: Output,
    ) -> FFMPEG:
        """
        Pad the media to a given width and height keeping the media centered.
        """

        self.filter_complex.append(
            f"[{input}]pad='{width}':'{height}':'(ow-iw)/2':'(oh-ih)/2':"
            f"color='{color}'[{output}];"
        )
        return self

    @RoundFloats()
    def crop(
        self,
        input: Input,
        x: Position,
        y: Position,
        width: Dimension,
        height: Dimension,
        output: Output,
    ) -> FFMPEG:
        """
        Crop the media to a given width and height.
        """

        self.filter_complex.append(
            f"[{input}]crop='{width}':'{height}':'{x}':'{y}'[{output}];"
        )
        return self

    @RoundFloats()
    def crop_from_center(
        self, input: Input, width: Dimension, height: Dimension, output: Output
    ) -> FFMPEG:
        """
        Crop the media to a given width and height from the center.
        """

        self.filter_complex.append(
            f"[{input}]crop='{width}':'{height}':'0':'ih/2-{width}/2'[{output}];"
        )
        return self

    @RoundFloats()
    def scale(
        self, input: Input, width: Dimension, height: Dimension, output: Output
    ) -> FFMPEG:
        """
        Scale the media to a given width and height.
        """

        self.filter_complex.append(
            f"[{input}]scale_cuda='{width}':'{height}'[{output}];"
        )
        return self

    @RoundFloats()
    def round_mask(self, input: Input, output: Output) -> FFMPEG:
        """
        Make a round mask for the media.
        """

        self.filter_complex.append(
            f"[{input}]trim=end_frame=1,"
            f"geq='st(3,pow(X-(W/2),2)+pow(Y-(H/2),2));if(lte(ld(3),pow(min(W/2,H/2),2)),255,"
            f"0)':128:128,setpts=N/FRAME_RATE/TB[{output}]; "
        )
        return self

    @RoundFloats()
    def merge_mask(self, input: Input, mask: Input, output: Output) -> FFMPEG:
        """
        Merge a mask with the media.
        """

        self.filter_complex.append(f"[{input}][{mask}]alphamerge[{output}];")
        return self

    def split_stream(self, input: Input, output_1: Output, output_2: Output) -> FFMPEG:
        """
        Split the media into two streams.
        """

        self.filter_complex.append(f"[{input}]split=[{output_1}][{output_2}];")
        return self

    @RoundFloats()
    def overlay(
        self,
        background: Input,
        overlay: Input,
        x: Position,
        y: Position,
        output: Output,
    ) -> FFMPEG:
        """
        Overlay the overlay_item on the background_item.
        """

        self.filter_complex.append(
            f"[{background}][{overlay}]overlay_cuda='{x}':'{y}'[{output}];"
        )
        return self

    @RoundFloats()
    def draw_text(
        self,
        input: Input,
        text: str,
        x: Position,
        y: Position,
        font_color: str,
        font_size: str,
        font_file: str,
        output: Output,
    ) -> FFMPEG:
        """
        Draw text on the media.
        """
        font_file = normalize_font_path(font_file)
        font_file = f"fontfile='{font_file}':"

        text = fix_ffmpeg_text(text)

        self.filter_complex.append(
            f"[{input}]drawtext={font_file}text='{text}':fontcolor='{font_color}':"
            f"fontsize='{font_size}':x='{x}':y='{y}'[{output}];"
        )
        return self

    @RoundFloats()
    def draw_box(
        self,
        input: Input,
        color: str,
        x: Position,
        y: Position,
        width: Dimension,
        height: Dimension,
        output: Output,
    ) -> FFMPEG:
        """
        Creates a box with given color and sizes

        @param input:
        @param color:
        @param x:
        @param y:
        @param width:
        @param height:
        @param output:
        @return:
        """
        self.filter_complex.append(
            f"[{input}]drawbox=x={x}:y={y}:color={color}:t=fill:w={width}:h={height}[{output}];"
        )

        return self

    @RoundFloats()
    def change_speed(self, input: Input, duration: Seconds, output: Output) -> FFMPEG:
        """
        Change the speed of the media.
        """
        speed = duration / 60

        self.filter_complex.append(f"[{input}]setpts='{speed}*PTS'[{output}];")
        return self

    def aspect_ratio(self, input: Input, aspect_ratio: str, output: Output) -> FFMPEG:
        """
        Set the aspect ratio of the media.

        @param input:
        @param aspect_ratio: Aspect ratio (Format: width/height)
        @param output:
        """

        if "/" not in aspect_ratio:
            warnings.warn(f"The aspect ratio {aspect_ratio} might not be valid.")

        self.filter_complex.append(f"[{input}]setdar={aspect_ratio}[{output}];")
        return self

    @RoundFloats()
    def repeat_last_frame(self, input: Input, duration: Seconds, output: str) -> FFMPEG:
        """
        Repeat the last frame of the media for n seconds.

        @param input
        @param duration:
        @param output:
        """

        self.filter_complex.append(
            f"[{input}]tpad=stop_mode=clone:stop_duration={duration}[{output}];"
        )
        return self

    def volume(self, input: Input, volume: Volume, output: str) -> FFMPEG:
        """
        Set the volume of the media.
        """

        self.filter_complex.append(f"[{input}]volume={volume}[{output}];")
        return self

    def concat(
        self,
        input: [(Input, Input)],
        output_video: str = None,
        output_audio: str = None,
    ) -> FFMPEG:
        """
        Concat media
        """
        filter = ""
        for i in input:
            if output_video:
                filter += f"[{i[0]}]"
            if output_audio:
                filter += f"[{i[1]}]"

        filter += f"concat=n={len(input)}:"

        if output_audio and output_audio:
            filter += f"v=1:a=1[{output_video}][{output_audio}];"
        elif output_video:
            filter += f"v=1[{output_video}];"
        elif output_audio:
            filter += f"a=1[{output_audio}];"

        self.filter_complex.append(filter)
        return self

    def amix(self, item_1: Input, item_2: Input, output: Output) -> FFMPEG:
        """
        Mix the media.
        """
        self.filter_complex.append(f"[{item_1}][{item_2}]amix=2[{output}];")
        return self

    def create_silent_audio_stream(self, output: Output, duration: int) -> FFMPEG:
        """ """
        self.filter_complex.append(
            f"anullsrc=channel_layout=stereo:sample_rate={self._bitrate}:d={duration}[{output}];"
        )
        return self

    def aresample(self, input: Input, output: Output) -> FFMPEG:
        """
        Resample the media.
        """

        self.filter_complex.append(f"[{input}]aresample={self.bitrate}[{output}];")
        return self

    """
        FILTER MODIFIERS
    """

    @RoundFloats()
    def between(self, start: Seconds, end: Seconds) -> FFMPEG:
        """
        When ran after a filter is added it will set the filter to only be rendered between
        the start second and the end second.

        This method does such by getting the last option and appending the "enable" between
        command to it before the output

        @param start:
        @param end:
        @return:
        """
        last_filter = self.filter_complex[-1]
        output = re.search("(\[\w*];)", last_filter).groups()[0]
        last_filter = last_filter.replace(output, "")

        self.filter_complex[-1] = (
            f"{last_filter}:enable='between(t,{start},{end})'{output}"
        )
        return self

    def map(self, input: Input) -> FFMPEG:
        """
        Map the media.
        """

        self.maps.extend(["-map", f"[{input}]"])
        return self

    """
        FILTERS COMMANDS END
    """

    def run(self) -> FFMPEG:
        """
        Run the compiled command.
        """

        if not self._output_added:
            raise Exception("Output file not added")
        process = subprocess.Popen(self.cmd, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()

        if process.returncode != 0:
            raise RuntimeError(
                f"ffmpeg exited with code {process.returncode}\n"
                f"{self.cmd}\n"
                f"Stdout: {process.stdout.read().decode('utf-8') if process.stdout else None}\n"
                f"Stdout: {process.stderr.read().decode('utf-8') if process.stderr else None}\n"
            )

        return self
