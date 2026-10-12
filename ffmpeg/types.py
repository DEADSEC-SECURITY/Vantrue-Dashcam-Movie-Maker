#  Copyright (c) 2022.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Built-In Imports
from typing import NewType, TypeVar

# 3rd-Party Imports

# Local Imports


Input = NewType("Input", str | int)
Output = str
Dimension = TypeVar("Dimension", str, int, float)
Position = NewType("Position", str | int | float)
Seconds = TypeVar("Seconds", str, int, float)
Volume = TypeVar("Volume", str, int)
Size = TypeVar("Size", str, int, float)
