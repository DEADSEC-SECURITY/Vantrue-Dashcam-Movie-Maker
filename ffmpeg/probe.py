#  Copyright (c) 2022.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
from __future__ import annotations

# 3rd-Party Imports
import subprocess

# Local Imports


class PROBE:
    """
        Interact with FFMPEG PROBE using python.
    """

    def __init__(self, ffprobe_path: str = 'ffprobe'):
        self.probe_path = ffprobe_path

        self._debug = False

        # Set default values
        self._set_defaults()

    def _set_defaults(self) -> None:
        """
            Set default values.
        """

        self.cmd = [self.probe_path]

    def _run(self) -> str:
        """
            Run the command built with the class and return the output.
        """

        process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE)
        process.wait()

        if process.returncode != 0:
            raise Exception(f'probe exited with code {process.returncode}')

        output = process.stdout.read().decode('utf-8')
        process.stdout.close()

        return output

    def reset(self) -> PROBE:
        """
            Reset the class to default values.
            Useful when you want to run different commands under the same instance.
        """

        self._set_defaults()

        return self

    def get_media_duration(self, input_file: str) -> int:
        """
            Get the media duration of the input file.
        """

        self.cmd.extend(
            [
                '-v', 'error',
                '-show_entries',
                'format=duration',
                '-of',
                'default=noprint_wrappers=1:nokey=1',
                input_file
            ]
        )

        process = self._run()
        length = process.strip()
        length = int(round(float(length), 0))

        self.reset()

        return length
