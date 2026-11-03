from typing import Annotated, override

from cl.app import BaseApplication, BaseApplicationConfig, OutputType, RunSummary
from cl.app.model import DurationSeconds
from pydantic import Field

from .play import play, visible_mix_seconds


class MyApplicationConfig(BaseApplicationConfig):
    duration: Annotated[
        DurationSeconds,
        Field(
            title="Duration",
            description="How long to listen for turns, in seconds.",
            default=90,
        ),
    ]
    scramble_turns: Annotated[
        int,
        Field(
            title="Scramble",
            description="How many turns to mix the 2x2x2 cube before solving.",
            default=6,
            ge=1,
            le=11,
        ),
    ]

    @override
    def estimate_duration_s(self) -> float:
        return self.duration + visible_mix_seconds(self.scramble_turns)


class MyApplication(BaseApplication[MyApplicationConfig]):
    @override
    def run(self, config: MyApplicationConfig, output_directory: str) -> RunSummary | None:
        _solved, text = play(config.duration, config.scramble_turns)
        return RunSummary(
            type=OutputType.TEXT,
            content=text,
        )

    @staticmethod
    @override
    def config_class() -> type[MyApplicationConfig]:
        return MyApplicationConfig
