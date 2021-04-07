import pytest
import os
from stackmanager.config import Config
from stackmanager.exceptions import ValidationError
from stackmanager.loader import load_config


def config_file(filename='config.yaml'):
    return os.path.join(os.path.dirname(__file__), filename)


def test_loader_dev():
    config = load_config(config_file(), Config({'Region': 'us-east-1'}), 'dev', False)

    assert config.environment == 'dev'
    assert config.region == 'us-east-1'
    assert config.template == 'integration/template.yaml'
    assert config.parameters == {
        'Environment': 'dev',
        'SSMKey': '/Company/d/us-east-1/Key',
        'Domain': 'dev.example.com',
        'KeyId': 'guid1'
    }
    assert config.tags == {
        'Application': 'Example',
        'Environment': 'dev'
    }
    assert config.capabilities == ['CAPABILITY_NAMED_IAM']


def test_loader_prod():
    config = load_config(config_file(), Config({'Region': 'us-east-2'}), 'prod', False)

    assert config.environment == 'prod'
    assert config.region == 'us-east-2'
    assert config.template == 'integration/template.yaml'
    assert config.parameters == {
        'Environment': 'prod',
        'SSMKey': '/Company/p/us-east-2/Key',
        'Domain': 'prod.example.com',
        'KeyId': 'guid4'
    }
    assert config.tags == {
        'Application': 'Example',
        'Environment': 'prod'
    }
    assert config.capabilities == ['CAPABILITY_NAMED_IAM']


def test_loader_dev_overrides():
    previous_parameters = ('Previous', 'LambdaKey')
    override_parameters = (
        ('SSMKey', '/Other/{{ Environment }}/Key'),
        ('Domain', 'notdev.example.com'),
        ('Extra', 'OverrideDefault'),
        ('LambdaKey', 'd/e/f')
    )

    arg_config = Config({})
    arg_config.region = 'us-east-1'
    arg_config.add_parameters({
        'LambdaBucket': 'mybucket',
        'LambdaKey': 'a/b/c'
    })
    config = load_config(config_file(), arg_config, 'dev', False,
                         Template='integration/config.yaml', Parameters=override_parameters,
                         PreviousParameters=previous_parameters, ChangeSetName='TestChangeSet', AutoApply=True)

    assert config.environment == 'dev'
    assert config.region == 'us-east-1'
    assert config.template == 'integration/config.yaml'
    assert config.parameters == {
        'Environment': 'dev',
        'SSMKey': '/Other/dev/Key',
        'Domain': 'notdev.example.com',
        'KeyId': 'guid1',
        'Extra': 'OverrideDefault',
        'LambdaBucket': 'mybucket',
        'LambdaKey': 'd/e/f',
        'Previous': '<<UsePreviousValue>>'
    }
    assert config.change_set_name == 'TestChangeSet'
    assert config.auto_apply is True


def test_loader_missing_environment():
    with pytest.raises(ValidationError, match='Environment test for us-east-1 not found in .*'):
        load_config(config_file(), Config({'Region': 'us-east-1'}), 'test')


def test_loader_missing_region():
    with pytest.raises(ValidationError, match='Environment dev for us-west-1 not found in .*'):
        load_config(config_file(), Config({'Region': 'us-west-1'}), 'dev')
