import shlex
import subprocess
import tempfile
import pytest
import json
import prefect
from cryptography.fernet import Fernet
from click.testing import CliRunner
from prefect.cli import cli


class SuccessTask(prefect.Task):
    def run(self):
        return 1


class PlusOneTask(prefect.Task):
    def run(self, x):
        return x + 1


class AddTask(prefect.Task):
    def run(self, x, y):
        return x + y


@pytest.fixture(autouse=True)
def clear_registry():
    yield
    prefect.core.registry.REGISTRY.clear()


def run_cli(cmd):
    return CliRunner().invoke(cli, shlex.split(cmd))


def run_cli_with_registry(cmd):
    """
    Runs a CLI cmd with flags appropriately set for the current registry
    """
    encryption_key = Fernet.generate_key().decode()
    with tempfile.NamedTemporaryFile() as tmp:
        with open(tmp.name, "wb") as f:
            f.write(
                prefect.core.registry.serialize_registry(encryption_key=encryption_key)
            )
        options = "--registry-path={} --registry-encryption-key={} ".format(
            tmp.name, encryption_key
        )
        return run_cli(options + cmd)


def test_flows_keys_empty_registry():
    output = json.loads(run_cli_with_registry("flows ids").output)
    assert output == {}


def test_flows_keys():
    f1 = prefect.Flow(register=True)
    f2 = prefect.Flow(name="hi", version="1", register=True)
    f3 = prefect.Flow(name="hi", version="2", register=True)

    output = json.loads(run_cli_with_registry("flows ids").output)
    assert output == {f.id: f.key() for f in [f1, f2, f3]}


def test_flows_runs():
    """
    Tests that the CLI runs a flow by creating a flow that writes to a known file and testing that the file is written.
    """

    @prefect.task
    def write_to_file(path):
        with open(path, "w") as f:
            f.write("1")

    with tempfile.NamedTemporaryFile() as tmp:
        with prefect.Flow(register=True) as f:
            write_to_file(tmp.name)

        run_cli_with_registry("flows run {}".format(f.id))

        with open(tmp.name, "r") as f:
            assert f.read() == "1"
