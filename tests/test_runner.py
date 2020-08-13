import pytest
import unittest.mock
from stackmanager.config import Config
from stackmanager.runner import Runner
from stackmanager.status import StackStatus

@pytest.fixture
def config():
    return Config({
        'StackName': 'TestStack',
        'Environment': 'test',
        'Region': 'us-east-1',
        'Parameters': {
            'Param1': 'Value1'
        },
        'Tags': {
            'Tag1': 'Value1'
        },
        'Capabilities': [
            'CAPABILITY_IAM'
        ]
    })


@pytest.fixture
def create_complete_stack():
    return {
        'Stacks': [{
            'StackName': 'TestStack',
            'StackStatus': StackStatus.CREATE_COMPLETE.name
        }]
    }


@pytest.fixture
def create_complete_client(create_complete_stack):
    attrs = {'describe_stacks.return_value': create_complete_stack}
    mock = unittest.mock.MagicMock(**attrs)
    return mock


def test_load_stack(create_complete_client, config):
    runner = Runner(create_complete_client, config)

    create_complete_client.describe_stacks.assert_called_once_with(StackName='TestStack')
    assert runner.change_set_name is not None
    assert runner.change_set_name.startswith('c')
