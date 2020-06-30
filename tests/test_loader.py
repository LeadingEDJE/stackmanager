import pytest
import os
from stackmanager.exceptions import ValidationError
from stackmanager.loader import load_config


def config_file(filename='config.yaml'):
    return os.path.join(os.path.dirname(__file__), filename)


def test_loader_dev():
    config = load_config(config_file(), 'dev', 'us-east-1', None, None)

    assert config.environment == 'dev'
    assert config.region == 'us-east-1'
    assert config.template == 'integration/template.yaml'
    assert config.parameters == {
        'Environment': 'dev',
        'SSMKey': '/Company/dev/us-east-1/Key',
        'Domain': 'dev.example.com',
        'KeyId': 'guid1'
    }
    assert config.tags == {
        'Application': 'Example',
        'Environment': 'dev'
    }
    assert config.capabilities == ['CAPABILITY_NAMED_IAM']


def test_loader_prod():
    config = load_config(config_file(), 'prod', 'us-east-2', None, None)

    assert config.environment == 'prod'
    assert config.region == 'us-east-2'
    assert config.template == 'integration/template.yaml'
    assert config.parameters == {
        'Environment': 'prod',
        'SSMKey': '/Company/prod/us-east-2/Key',
        'Domain': 'prod.example.com',
        'KeyId': 'guid4'
    }
    assert config.tags == {
        'Application': 'Example',
        'Environment': 'prod'
    }
    assert config.capabilities == ['CAPABILITY_NAMED_IAM']


def test_loader_dev_overrides():
    override_parameters = [
        ('SSMKey', '/Other/{{ Environment }}/Key'),
        ('Domain', 'notdev.example.com'),
        ('Extra', 'OverrideDefault')
    ]
    config = load_config(config_file(), 'dev', 'us-east-1', 'integration/config.yaml', override_parameters)

    assert config.environment == 'dev'
    assert config.region == 'us-east-1'
    assert config.template == 'integration/config.yaml'
    assert config.parameters == {
        'Environment': 'dev',
        'SSMKey': '/Other/dev/Key',
        'Domain': 'notdev.example.com',
        'KeyId': 'guid1',
        'Extra': 'OverrideDefault'
    }


def test_loader_missing_environment():
    with pytest.raises(ValidationError, match='Environment test for us-east-1 not found in .*'):
        load_config(config_file(), 'test', 'us-east-1', None, None)


def test_loader_missing_region():
    with pytest.raises(ValidationError, match='Environment dev for us-west-1 not found in .*'):
        load_config(config_file(), 'dev', 'us-west-1', None, None)
