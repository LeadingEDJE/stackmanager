import os
import pytest
import stackmanager.packager
import tempfile
from aws_lambda_builders.builder import LambdaBuilder
from stackmanager.exceptions import ValidationError


functions_dir = os.path.join(os.path.dirname(__file__), '..', 'integration', 'functions')


def test_get_config_single():
    config = stackmanager.packager.get_config('python3.11', os.path.join(functions_dir, 'python'))
    assert config == stackmanager.packager.PYTHON_PIP_CONFIG


def test_get_config_match_manifest():
    config = stackmanager.packager.get_config('java11', os.path.join(functions_dir, 'java-gradle',
                                                                     'HelloWorldFunction'))
    assert config == stackmanager.packager.JAVA_GRADLE_CONFIG


def test_get_config_unsupported_runtime():
    with pytest.raises(ValidationError, match='Unsupported Runtime foo2.1'):
        stackmanager.packager.get_config('foo2.1', '.')


def test_get_config_missing_manifest():
    with pytest.raises(ValidationError, match='Cannot find suitable manifest for Runtime java11'):
        stackmanager.packager.get_config('java11', os.path.join(functions_dir, 'python'))


def test_build_lambda(capsys, monkeypatch):
    def build(source_dir, artifacts_dir, scratch_dir, manifest_path, runtime=None, optimizations=None, options=None,
              executable_search_paths=None, mode=None):
        pass

    monkeypatch.setattr(LambdaBuilder, 'build', build)

    with tempfile.TemporaryDirectory() as output_dir:
        stackmanager.packager.build_lambda(os.path.join(functions_dir, 'python'), output_dir, 'python3.11', 'test')

        assert os.path.isfile(os.path.join(output_dir, 'test.zip'))

    captured = capsys.readouterr()
    assert 'Building python3.11 Lambda function from' in captured.out
    assert 'Built Lambda Archive' in captured.out
