# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import click
import pytest

from sunbeam.plugins.validation import plugin as validation_plugin


@pytest.fixture(autouse=True)
def mock_run_sync(mocker):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    def run_sync(coro):
        return loop.run_until_complete(coro)

    mocker.patch("sunbeam.plugins.validation.plugin.run_sync", run_sync)
    yield
    loop.close()


@pytest.fixture()
def cclient():
    with patch("sunbeam.plugins.interface.v1.base.Client") as p:
        yield p


@pytest.fixture()
def jhelper():
    yield AsyncMock()


@pytest.fixture()
def tfhelper():
    yield Mock(path=Path())


@pytest.fixture()
def validationplugin():
    with patch("sunbeam.plugins.validation.plugin.ValidationPlugin") as p:
        yield p


class TestValidatorFunction:
    """Test validator functions."""

    @pytest.mark.parametrize(
        "input_schedule",
        [
            "",
            "5 4 * * *",
            "5 4 * * mon",
            "*/30 * * * *",
        ],
    )
    def test_valid_cron_expressions(self, input_schedule):
        """Verify valid cron expressions."""
        assert validation_plugin.validated_schedule(input_schedule) == input_schedule

    @pytest.mark.parametrize(
        "test_input,expected_msg",
        [
            ("*/5 * * * *", "Cannot schedule periodic check"),
            ("*/30 * * * * 6", "This cron does not support"),
            ("*/30 * *", "Exactly 5 columns must"),
            ("*/5 * * * xyz", "not acceptable"),
        ],
    )
    def test_invalid_cron_expressions(self, test_input, expected_msg):
        """Verify invalid cron expressions."""
        with pytest.raises(click.ClickException) as e:
            schedule = validation_plugin.validated_schedule(test_input)
            assert schedule == ""
        assert expected_msg in str(e)
