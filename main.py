import datetime
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from ffmpeg.ffmpeg import FFMPEG
from ffmpeg.types import Input
from ffmpeg.probe import PROBE

DEBUG = False

LOCAL_DIR = pathlib.Path.cwd()
INPUT_DIR = LOCAL_DIR.joinpath("test_input") if DEBUG else LOCAL_DIR.joinpath("input")

PROBE = PROBE()

FFMPEG_COMPILING_SPEED = (
    1.5  # Average speed FFMPEG compiles the videos with current settings
)


def datetime_from_file_name(file: pathlib.Path) -> datetime.datetime:
    file_name_datetime_section = file.name.split(".")[0][:15]
    datetime_ = datetime.datetime.strptime(file_name_datetime_section, "%Y%m%d_%H%M%S")
    return datetime_


class VideoTypes(Enum):
    Parked = 0
    Moving = 1


class VideoViewPointType(Enum):
    Front = 0
    Back = 1


@dataclass
class Video:
    ffmpeg: FFMPEG
    path: pathlib.Path
    view_point: VideoViewPointType
    type_: VideoTypes
    duration_seconds: Optional[int]
    ffmpeg_input_number: Input = 0
    ffmpeg_video_stream: Input = "0:v"
    ffmpeg_audio_stream: Input = "0:a"

    def __init__(self, ffmpeg: FFMPEG, path: pathlib.Path):
        self.ffmpeg = ffmpeg
        self.path = path

        file_name = path.name.split(".")[0]
        if "P" in file_name:
            self.type_ = VideoTypes.Parked
        else:
            self.type_ = VideoTypes.Moving

        if "A" in file_name:
            self.view_point = VideoViewPointType.Front
        else:
            self.view_point = VideoViewPointType.Back

        try:
            self.duration_seconds = PROBE.get_media_duration(self.path.as_posix())
        except Exception:
            self.duration_seconds = None

    def add_as_ffmpeg_input(self):
        self.ffmpeg.add_input(self.path.as_posix())
        self.ffmpeg_input_number = self.ffmpeg.current_input_index
        self.ffmpeg_video_stream = f"{self.ffmpeg.current_input_index}:v"
        self.ffmpeg_audio_stream = f"{self.ffmpeg.current_input_index}:a"

        if (
            self.type_ == VideoTypes.Parked
            and self.view_point == VideoViewPointType.Front
        ):
            self.add_audio_stream()

    def add_audio_stream(self):
        """
        Adds a silent audio stream to the video, so it can be used in concat

        :return:
        """
        self.ffmpeg_audio_stream = f"a_{self.ffmpeg_input_number}"
        self.ffmpeg.create_silent_audio_stream(
            self.ffmpeg_audio_stream, self.duration_seconds
        )


@dataclass
class VideoGroup:
    ffmpeg: FFMPEG
    title: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    front_videos: [Video]
    back_videos: [Video]
    final_video: Optional[pathlib.Path]

    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        videos: List[pathlib.Path],
        ffmpeg: Optional[FFMPEG] = None,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.front_videos = []
        self.back_videos = []
        self.final_video = None

        self.ffmpeg = ffmpeg
        if not ffmpeg:
            self.ffmpeg = FFMPEG(use_gpu=True)

        # Configure FFMPEG
        self.ffmpeg.debug = DEBUG

        for video in videos:
            self.add_video(video)

        # Create title
        self.title = self.start_time.strftime("%d %b %Y %H-%M-%S")

    def add_video(self, video: pathlib.Path):
        video = Video(self.ffmpeg, video)

        if video.duration_seconds is None:
            return

        if video.view_point == VideoViewPointType.Front:
            self.front_videos.append(video)
            return

        self.back_videos.append(video)

    @property
    def total_seconds(self):
        """
        This is the amount of seconds between the start of the first video and the end of the last in the group

        :return:
        """
        return (self.end_time - self.start_time).total_seconds()

    @property
    def total_real_minutes(self):
        """
        This is the total minutes the video will have after all media added

        :return:
        """
        return len(self.front_videos)

    @property
    def has_missing_pair(self) -> bool:
        """
        Checks if the amount of front videos matches the amount of back videos

        :return:
        """
        return len(self.front_videos) != len(self.back_videos)

    def make_video(self):
        final_output_file = pathlib.Path(f"{self.title}.mp4")

        if final_output_file.exists() and not DEBUG:
            print("Skipping ... Already exists")
            return

        front_and_back_videos = list(zip(self.front_videos, self.back_videos))
        batches: List[Tuple[Video, Video]] = [
            front_and_back_videos[i : i + 4]
            for i in range(0, len(front_and_back_videos), 4)
        ]

        batch_files = []
        for index, batch in enumerate(batches):
            output_file = pathlib.Path(f"{self.title}_{index}.mp4")
            batch_files.append(output_file)

            self.ffmpeg.reset()

            for front_video, back_video in batch:
                front_video.add_as_ffmpeg_input()
                back_video.add_as_ffmpeg_input()

            self.ffmpeg.concat(
                input=[
                    (video.ffmpeg_video_stream, video.ffmpeg_audio_stream)
                    for (video, _) in batch
                ],
                output_video="front_v",
                output_audio="front_a",
            ).concat(
                input=[
                    (video.ffmpeg_video_stream, video.ffmpeg_audio_stream)
                    for (_, video) in batch
                ],
                output_video="back_v",
            ).scale(
                input="back_v", width=1920 / 1.5, height=1080 / 1.5, output="back_v"
            ).overlay(
                background="front_v", overlay="back_v", x=0, y=0, output="v"
            ).map(
                "v"
            ).map(
                "front_a"
            ).add_output(
                output_file.as_posix()
            )

            if DEBUG:
                print(self.ffmpeg)
                input("PRESS ENTER TO RUN")

            self.ffmpeg.run()

        cmd = ["ffmpeg"]
        for batch_file in batch_files:
            cmd.extend(["-i", batch_file])

        cmd.extend(
            [
                "-filter_complex",
                f"concat=n={len(batch_files)}:v=1:a=1",
                "-c:v",
                "h264_nvenc",
                "-preset",
                "slow",
                "-qp",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "44100",
                final_output_file,
            ]
        )
        process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()

        self.final_video = final_output_file


def display_table(videos: List[VideoGroup]):
    print(f"Total Videos: {len(videos)}")
    table = Table()

    # Add columns
    columns = [
        "Start Time",
        "End Time",
        "Total Videos",
        "Total Front Videos",
        "Total Back Videos",
        "Total Minutes",
        "Has Missing Videos",
        "Compiling Time",
        "Final Video",
    ]
    for column in columns:
        table.add_column(column)

    totals = {"front_videos": 0, "back_videos": 0, "minutes": 0}
    for video in videos:
        front_videos = len(video.front_videos)
        back_videos = len(video.back_videos)
        minutes = video.total_seconds // 60

        # Add to totals
        totals["front_videos"] += front_videos
        totals["back_videos"] += back_videos
        totals["minutes"] += minutes

        # Add row
        table.add_row(
            str(video.start_time),
            str(video.end_time),
            str(front_videos + back_videos),
            str(front_videos),
            str(back_videos),
            str(minutes),
            str(video.has_missing_pair),
            str(datetime.timedelta(minutes=len(video.front_videos))),
            str(video.final_video),
        )

    # Add total row
    table.add_section()
    table.add_row(
        "",
        "Totals",
        str(totals["front_videos"] + totals["back_videos"]),
        str(totals["front_videos"]),
        str(totals["back_videos"]),
        str(totals["minutes"]),
        "Total Compiling Time",
        str(
            datetime.timedelta(minutes=totals["front_videos"] / FFMPEG_COMPILING_SPEED)
        ),
    )

    console = Console()
    console.print(table)


def get_videos() -> List[VideoGroup]:
    videos: List[VideoGroup] = []

    files = list(INPUT_DIR.iterdir())
    for file in tqdm(files, desc="Loading Videos"):
        file_datetime = datetime_from_file_name(file)

        found_group = False
        for video in videos:
            # Check if the current file is within N time of the last video clip
            if file_datetime - datetime.timedelta(hours=2) < video.end_time:
                video.end_time = file_datetime
                video.add_video(file)
                found_group = True
                break

        if not found_group:
            videos.append(
                VideoGroup(
                    start_time=file_datetime, end_time=file_datetime, videos=[file]
                )
            )

    return videos


if __name__ == "__main__":
    vs = get_videos()
    # vs.sort(key=lambda x: x.total_real_minutes)
    display_table(vs)
    input("Press ENTER to start compiling media")
    for v in tqdm(vs, desc="Processing Videos"):
        v.make_video()
        display_table(vs)
