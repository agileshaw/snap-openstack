# Copyright (c) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import click
from croniter import croniter
from packaging.version import Version
from rich.console import Console

from sunbeam.clusterd.client import Client
from sunbeam.clusterd.service import ClusterServiceUnavailableException
from sunbeam.commands.openstack import OPENSTACK_MODEL
from sunbeam.jobs.juju import JujuHelper, run_sync
from sunbeam.jobs.plugin import PluginManager
from sunbeam.plugins.interface.v1.openstack import (
    OpenStackControlPlanePlugin,
    TerraformPlanLocation,
)

LOG = logging.getLogger(__name__)
console = Console()

PLUGIN_VERSION = "0.0.1"
MINIMAL_PERIOD = 15 * 60
TEMPEST_CHANNEL = "latest/edge"
VALIDATION_PLUGIN_DEPLOY_TIMEOUT = 60 * 60  # tempest can take some time to initialized


def validated_schedule(schedule: str) -> str:
    """Validate the schedule config option.

    Return the valid schedule if valid,
    otherwise Raise a click BadParameter exception.
    """
    # Empty schedule is fine; it means it's disabled in this context.
    if not schedule:
        return ""

    # croniter supports second repeats, but vixie cron does not.
    if len(schedule.split()) == 6:
        raise click.ClickException(
            "This cron does not support seconds in schedule (6 fields)."
            " Exactly 5 columns must be specified for iterator expression."
        )

    # constant base time for consistency
    base = datetime(2004, 3, 5)

    try:
        cron = croniter(schedule, base, max_years_between_matches=1)
    except ValueError as e:
        msg = str(e)
        # croniter supports second repeats, but vixie cron does not,
        # so update the error message here to suit.
        if "Exactly 5 or 6 columns" in msg:
            msg = "Exactly 5 columns must be specified for iterator expression."
        raise click.ClickException(msg)

    # This is a rather naive method for enforcing this,
    # and it may be possible to craft an expression
    # that results in some consecutive runs within 15 minutes,
    # however this is fine, as there is process locking for tempest,
    # and this is more of a sanity check than a security requirement.
    t1 = cron.get_next()
    t2 = cron.get_next()
    if t2 - t1 <= MINIMAL_PERIOD:
        raise click.ClickException(
            "Cannot schedule periodic check to run faster than every 15 minutes."
        )

    return schedule


@dataclass()
class Config:
    """Represents config updates provided by the user.

    None values mean the user did not provide them.
    """

    schedule: Optional[str] = None


def parse_config_args(args: List[str]) -> Dict[str, str]:
    """Parse key=value args into a valid dictionary of key: values.

    Raise a click bad argument error if errors (only checks syntax here).
    """
    config = {}
    for arg in args:
        split_arg = arg.split("=", 1)
        if len(split_arg) == 1:
            raise click.ClickException("syntax: key=value")
        key, value = split_arg
        if key in config:
            raise click.ClickException(
                f"{key} parameter seen multiple times.  Only provide it once."
            )
        config[key] = value
    return config


def validated_config_args(args: Dict[str, str]) -> Config:
    """Validate config and return validated config if no errors.

    Raise a click bad argument error if errors.
    """

    config = Config()

    for key, value in args.items():
        if key == "schedule":
            config.schedule = validated_schedule(value)
        else:
            raise click.ClickException(f"{key} is not a supported config option")

    return config


class ValidationPlugin(OpenStackControlPlanePlugin):
    """Deploy tempest to openstack model."""

    version = Version(PLUGIN_VERSION)

    def __init__(self, client: Client) -> None:
        """Initialize the plugin class."""
        super().__init__(
            "validation",
            client,
            tf_plan_location=TerraformPlanLocation.SUNBEAM_TERRAFORM_REPO,
        )

    def set_application_names(self) -> list:
        """Application names handled by the terraform plan."""
        return ["tempest"]

    def set_tfvars_on_enable(self) -> dict:
        """Set terraform variables to enable the application."""
        return {
            "enable-validation": True,
            "tempest-channel": TEMPEST_CHANNEL,
        }

    def set_application_timeout_on_enable(self) -> int:
        """Set Application Timeout on enabling the plugin.

        The plugin plan will timeout if the applications
        are not in active status within in this time.
        """
        return VALIDATION_PLUGIN_DEPLOY_TIMEOUT

    def set_application_timeout_on_disable(self) -> int:
        """Set Application Timeout on disabling the plugin.

        The plugin plan will timeout if the applications
        are not removed within this time.
        """
        return VALIDATION_PLUGIN_DEPLOY_TIMEOUT

    def set_tfvars_on_disable(self) -> dict:
        """Set terraform variables to disable the application."""
        return {"enable-validation": False}

    def set_tfvars_on_resize(self) -> dict:
        """Set terraform variables to resize the application."""
        return {}

    def _run_action(
        self,
        action_name: str,
        action_params: Optional[dict] = None,
        progress_message: str = "",
        print_stdout: bool = False,
    ) -> None:
        """Run the charm's action."""
        jhelper = JujuHelper(self.client, self.snap.paths.user_data)
        with console.status(progress_message):
            app = "tempest"
            model = OPENSTACK_MODEL
            unit = run_sync(jhelper.get_leader_unit(app, model))
            if not unit:
                message = f"Unable to get {app} leader"
                raise click.ClickException(message)

            action_result = run_sync(
                jhelper.run_action(
                    unit,
                    model,
                    action_name,
                    action_params or {},
                )
            )

            if action_result.get("return-code", 0) > 1:
                message = f"Unable to run action: {action_name}"
                raise click.ClickException(message)

            if print_stdout:
                console.print(action_result.get("stdout").strip())

    def _configure_preflight_check(self) -> False:
        """Preflight check for configure command."""
        enabled_plugins = PluginManager.enabled_plugins(self.client)
        if "observability" not in enabled_plugins:
            return False
        return True

    @click.command()
    def enable_plugin(self) -> None:
        """Enable OpenStack Integration Test Suite (tempest)."""
        super().enable_plugin()

    @click.command()
    def disable_plugin(self) -> None:
        """Disable OpenStack Integration Test Suite (tempest)."""
        super().disable_plugin()

    @click.command()
    @click.argument("options", nargs=-1)
    def configure_validation(self, options: Optional[List[str]] = None) -> None:
        """Configure validation plugin.

        Run without arguments to view available configuration options.

        Run with key=value args to set configuration values.
        For example: sunbeam configure validation schedule="*/30 * * * *"
        """
        if not self._configure_preflight_check():
            raise click.ClickException(
                "'observability' plugin is required for configuring validation plugin."
            )

        if not options:
            console.print(
                "Config options available: \n\n"
                "schedule: set a cron schedule for running periodic tests.  Empty disables.\n\n"
                "Run with key=value args to set configuration values.\n"
                'For example: sunbeam configure validation schedule="*/30 * * * *"'
            )
            return

        config_changes = validated_config_args(parse_config_args(options))

        if config_changes.schedule is not None:
            jhelper = JujuHelper(self.client, self.snap.paths.user_data)
            with console.status("Configuring validation plugin ..."):
                app = "tempest"
                model = OPENSTACK_MODEL
                unit = run_sync(jhelper.get_leader_unit(app, model))
                if not unit:
                    message = f"Unable to get {app} leader"
                    raise click.ClickException(message)

                run_sync(
                    jhelper.set_application_config(
                        model, app, config={"schedule": config_changes.schedule}
                    )
                )
                console.print(message)

    @click.command()
    @click.option(
        "-s",
        "--smoke",
        is_flag=True,
        default=False,
        help="Run the smoke tests only. Equivalent to --regex=smoke.  If --regex and --smoke are provided, --regex is ignored.",
    )
    @click.option(
        "-r",
        "--regex",
        default="",
        help=(
            "A list of regexes, whitespace separated, used to select tests from"
            " the list."
        ),
    )
    @click.option(
        "-e",
        "--exclude-regex",
        default="",
        help="A single regex to exclude tests.",
    )
    @click.option(
        "-t",
        "--serial",
        is_flag=True,
        default=False,
        help="Run tests serially. By default, tests run in parallel.",
    )
    @click.option(
        "-l",
        "--test-list",
        default="",
        help=(
            "Use a predefined test list. See `sunbeam validation-lists`"
            " for available test lists."
        ),
    )
    def run_validate_action(
        self,
        smoke: bool = False,
        regex: str = "",
        exclude_regex: str = "",
        serial: bool = False,
        test_list: str = "",
    ) -> None:
        """Run a set of tests on the sunbeam installation."""
        action_name = "validate"
        action_params = {
            "regex": "smoke" if smoke else regex,
            "exclude-regex": exclude_regex,
            "serial": serial,
            "test-list": test_list,
        }
        progress_message = "Running tempest to validate the sunbeam deployment ..."
        self._run_action(
            action_name,
            action_params=action_params,
            progress_message=progress_message,
            print_stdout=True,
        )

    @click.command()
    def run_get_lists_action(self) -> None:
        """Get supported test lists for validation."""
        action_name = "get-lists"
        progress_message = "Retrieving existing test lists from tempest charm ..."
        self._run_action(
            action_name,
            action_params={},
            progress_message=progress_message,
            print_stdout=True,
        )

    @click.group()
    def validation_groups(self):
        """Manage cloud validation functionality."""

    def commands(self) -> dict:
        """Dict of clickgroup along with commands."""
        commands = super().commands()
        try:
            enabled = self.enabled
        except ClusterServiceUnavailableException:
            LOG.debug(
                "Failed to query for plugin status, is cloud bootstrapped ?",
                exc_info=True,
            )
            enabled = False

        if enabled:
            commands.update(
                {
                    # add the validation subcommand group to the root group:
                    # sunbeam validation ...
                    "init": [{"name": "validation", "command": self.validation_groups}],
                    # sunbeam configure validation ...
                    "configure": [
                        {"name": "validation", "command": self.configure_validation}
                    ],
                    # add the subcommands:
                    # sunbeam validation run ... etc.
                    "validation": [
                        {"name": "run", "command": self.run_validate_action},
                        {"name": "test-lists", "command": self.run_get_lists_action},
                    ],
                }
            )
        return commands
