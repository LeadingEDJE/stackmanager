import pytest
from click.testing import CliRunner
from stackmanager.cli import cli
from stackmanager.config import Config
from unittest.mock import patch


@pytest.fixture
def config():
    return Config({})


def test_deploy(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['deploy', '-p', 'dev', '-r', 'us-east-1', '-e', 'env', '-c', 'config.yml',
                                             '-t', 'template.yml', '--parameter', 'foo', 'bar',
                                             '--parameter-use-previous', 'keep', '--change-set-name',
                                             'testchangeset', '--auto-apply'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env',
                                                Template='template.yml', Parameters=(('foo', 'bar'),),
                                                PreviousParameters=('keep',), ChangeSetName='testchangeset',
                                                ExistingChanges='ALLOW', AutoApply=True)
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.deploy.assert_called_once()


def test_apply_change_set_name(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-r', 'us-east-1', 'apply', '-p', 'dev', '-e', 'env', '-c', 'config.yml',
                                             '--change-set-name', 'testchangeset'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env', False,
                                                ChangeSetName='testchangeset')
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.apply_change_set.assert_called_once()


def test_apply_change_set_id(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_changeset_runner') as create_changeset_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-r', 'us-east-1', 'apply', '-p', 'dev', '--change-set-id', 'id123'])

            assert result.exit_code == 0
            create_changeset_runner.assert_called_once_with('dev', 'us-east-1', 'id123')
            create_changeset_runner.return_value.apply_change_set.assert_called_once()


def test_reject_change_set_name(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-r', 'us-east-1', 'reject', '-p', 'dev', '-e', 'env', '-c', 'config.yml',
                                             '--change-set-name', 'testchangeset'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env', False,
                                                ChangeSetName='testchangeset')
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.reject_change_set.assert_called_once()


def test_reject_change_set_id(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_changeset_runner') as create_changeset_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-r', 'us-east-1', 'reject', '-p', 'dev', '--change-set-id', 'id123'])

            assert result.exit_code == 0
            create_changeset_runner.assert_called_once_with('dev', 'us-east-1', 'id123')
            create_changeset_runner.return_value.reject_change_set.assert_called_once()


def test_delete(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:
            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-r', 'us-east-1', 'delete', '--yes', '-p', 'dev', '-e', 'env',
                                             '-c', 'config.yml'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env', False)
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.delete.assert_called_once_with(())


def test_status(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:

            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-p', 'dev', 'status', '-r', 'us-east-1', '-e', 'env', '-c', 'config.yml'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env', False)
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.status.assert_called_once_with(7)


def test_get_output(config):
    with patch('stackmanager.cli.load_config') as load_config:
        load_config.return_value = config
        with patch('stackmanager.cli.create_runner') as create_runner:
            create_runner.return_value.configure_mock(**{'get_output.return_value': 'TestOutputValue'})

            cli_runner = CliRunner()
            result = cli_runner.invoke(cli, ['-p', 'dev', 'get-output', '-r', 'us-east-1', '-e', 'env', '-c',
                                             'config.yml', '-o', 'TestOutputKey'])

            assert result.exit_code == 0
            load_config.assert_called_once_with('config.yml', Config({'Region': 'us-east-1'}), 'env', False)
            create_runner.assert_called_once_with('dev', config)
            create_runner.return_value.get_output.assert_called_once_with('TestOutputKey')

            assert result.output == 'TestOutputValue\n'


def test_build_lambda():
    with patch('stackmanager.packager.build_lambda') as build_lambda:
        runner = CliRunner()
        result = runner.invoke(cli, ['build-lambda', '-s', 'src/', '-o', '.', '--runtime', 'python3.8',
                                     '--archive-name', 'MyFunction'])
        assert result.exit_code == 0
        build_lambda.assert_called_once_with('src/', '.', 'python3.8', 'MyFunction')


def test_upload():
    with patch('stackmanager.cli.create_uploader') as create_uploader:
        runner = CliRunner()
        result = runner.invoke(cli, ['upload', '-p', 'dev', '-r', 'us-east-1', '-f', 'my.zip', '-b', 'bucket', '-k',
                                     'key'])
        assert result.exit_code == 0
        create_uploader.assert_called_once_with('dev', 'us-east-1')
        create_uploader.return_value.upload.assert_called_once_with('my.zip', 'bucket', 'key')


def test_chained_commands(config):
    args = ['-p', 'dev', '-r', 'us-east-1',
            'build-lambda', '-s', 'src/', '-o', '.', '--runtime', 'python3.8',
            'upload', '-b', 'bucket', '-k', 'key',
            'deploy', '-e', 'env', '-c', 'config.yml']

    arg_config = Config({
        'Region': 'us-east-1',
        'Parameters': {
            'LambdaBucket': 'bucket',
            'LambdaKey': 'key'
        }
    })

    with patch('stackmanager.packager.build_lambda') as build_lambda:
        build_lambda.return_value = 'src.zip'
        with patch('stackmanager.cli.create_uploader') as create_uploader:
            with patch('stackmanager.cli.load_config') as load_config:
                load_config.return_value = config
                with patch('stackmanager.cli.create_runner') as create_runner:
                    runner = CliRunner()
                    result = runner.invoke(cli, args)

                    assert result.exit_code == 0
                    build_lambda.assert_called_once_with('src/', '.', 'python3.8', None)
                    create_uploader.assert_called_once_with('dev', 'us-east-1')
                    create_uploader.return_value.upload.assert_called_once_with('src.zip', 'bucket', 'key')
                    load_config.assert_called_once_with('config.yml', arg_config, 'env',
                                                        Template=None, Parameters=(), PreviousParameters=(),
                                                        ChangeSetName=None, ExistingChanges='ALLOW', AutoApply=False)
                    create_runner.assert_called_once_with('dev', config)
                    create_runner.return_value.deploy.assert_called_once()
