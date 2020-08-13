import os
import pytest
from botocore.exceptions import ClientError, WaiterError
from stackmanager.config import Config
from stackmanager.exceptions import StackError, ValidationError
from stackmanager.runner import Runner
from stackmanager.status import StackStatus
from unittest.mock import MagicMock


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
        ],
        'Template': os.path.join(os.path.dirname(__file__), 'template.yaml'),
        'ExistingChanges': 'ALLOW',
        'ChangeSetName': 'TestChangeSet'
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
def single_successful_changeset():
    return {
        'Summaries': [{
            'ChangeSetName': 'ExistingChangeSet',
            'CreationTime': '2020-01-01T00:00:00.00000+0000',
            'Status': 'CREATE_COMPLETE'
        }]
    }


@pytest.fixture
def describe_changeset():
    return {
        'Changes': [{
            'ResourceChange': {
                'Action': 'Add',
                'LogicalResourceId': 'Queue',
                'ResourceType': 'AWS::SQS::Queue'
            }
        }]
    }


@pytest.fixture
def before_and_after_events():
    return [
        {
            'StackEvents': [
                {
                    'Timestamp': '2020-01-01T12:00:00.00000-0000',
                    'LogicalResourceId': 'TestStack',
                    'ResourceType': 'AWS::CloudFormation::Stack',
                    'ResourceStatus': 'CREATE_COMPLETE'
                },
                {
                    'Timestamp': '2020-01-01T11:58:20.12436-0000',
                    'LogicalResourceId': 'Topic',
                    'ResourceType': 'AWS::SNS::Topic',
                    'ResourceStatus': 'CREATE_COMPLETE'
                }
            ]
        },
        {
            'StackEvents': [
                {
                    'Timestamp': '2020-01-01T13:25:01.32464-0000',
                    'LogicalResourceId': 'TestStack',
                    'ResourceType': 'AWS::CloudFormation::Stack',
                    'ResourceStatus': 'UPDATE_COMPLETE',
                },
                {
                    'Timestamp': '2020-01-01T13:24:53.34531-0000',
                    'LogicalResourceId': 'Queue',
                    'ResourceType': 'AWS::SQS::Queue',
                    'ResourceStatus': 'CREATE_COMPLETE'
                },
                {
                    'Timestamp': '2020-01-01T13:23:11.64372-0000',
                    'LogicalResourceId': 'TestStack',
                    'ResourceType': 'AWS::CloudFormation::Stack',
                    'ResourceStatus': 'UPDATE_IN_PROGRESS',
                    'ResourceStatusReason': 'User Initiated'
                },
                {
                    'Timestamp': '2020-01-01T12:00:00.00000-0000',
                    'LogicalResourceId': 'TestStack',
                    'ResourceType': 'AWS::CloudFormation::Stack',
                    'ResourceStatus': 'CREATE_COMPLETE'
                },
                {
                    'Timestamp': '2020-01-01T11:58:20.12436-0000',
                    'LogicalResourceId': 'Topic',
                    'ResourceType': 'AWS::SNS::Topic',
                    'ResourceStatus': 'CREATE_COMPLETE'
                }
            ]
        }
    ]


@pytest.fixture
def create_complete_client(create_complete_stack, single_successful_changeset, describe_changeset,
                           before_and_after_events):
    paginator_mock = MagicMock(**{'paginate.return_value': [before_and_after_events[1]]})
    attrs = {
        'describe_stacks.return_value': create_complete_stack,
        'list_change_sets.return_value': single_successful_changeset,
        'create_change_set.return_value': {'Id': 'TestChangeSetId'},
        'describe_change_set.return_value': describe_changeset,
        'describe_stack_events.return_value': before_and_after_events[0],
        'get_paginator.return_value': paginator_mock
    }
    mock = MagicMock(**attrs)
    return mock


def test_load_stack(create_complete_client, config, capsys):
    runner = Runner(create_complete_client, config)

    create_complete_client.describe_stacks.assert_called_once_with(StackName='TestStack')
    assert runner.stack is not None
    assert runner.change_set_name == 'TestChangeSet'

    captured = capsys.readouterr()
    assert captured.out == '\nStack: TestStack, Status: CREATE_COMPLETE\n'


def test_load_stack_does_not_exist(config, capsys):
    attrs = {'describe_stacks.side_effect': ClientError(error_response={}, operation_name='describe_stacks')}
    mock = MagicMock(**attrs)
    runner = Runner(mock, config)

    mock.describe_stacks.assert_called_once_with(StackName='TestStack')
    assert runner.stack is None
    assert runner.change_set_name == 'TestChangeSet'

    captured = capsys.readouterr()
    assert captured.out == '\nStack: TestStack, Status: does not exist\n'


def test_deploy_disallow_existing_changes(create_complete_client, config):
    runner = Runner(create_complete_client, config)
    config.config['ExistingChanges'] = 'DISALLOW'

    with pytest.raises(ValidationError, match='Creation of new ChangeSet not allowed when existing ChangeSets found'):
        runner.deploy()

    create_complete_client.list_change_sets.assert_called_once_with(StackName='TestStack')


def test_deploy_failed_only_existing_changes(create_complete_client, config):
    runner = Runner(create_complete_client, config)
    config.config['ExistingChanges'] = 'FAILED_ONLY'

    with pytest.raises(ValidationError,
                       match='Creation of new ChangeSet not allowed when existing valid ChangeSets found'):
        runner.deploy()

    create_complete_client.list_change_sets.assert_called_once_with(StackName='TestStack')


def test_deploy(create_complete_client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    runner = Runner(create_complete_client, config)
    runner.deploy()

    create_complete_client.list_change_sets.assert_called_once_with(StackName='TestStack')
    create_complete_client.create_change_set.assert_called_once_with(
        StackName='TestStack',
        ChangeSetName='TestChangeSet',
        ChangeSetType='UPDATE',
        Parameters=[{'ParameterKey': 'Param1', 'ParameterValue': 'Value1'}],
        Tags=[{'Key': 'Tag1', 'Value': 'Value1'}],
        Capabilities=['CAPABILITY_IAM'],
        TemplateBody='AWSTemplateFormatVersion : "2010-09-09"'
    )
    create_complete_client.get_waiter.assert_called_once_with('change_set_create_complete')
    create_complete_client.get_waiter().wait.assert_called_once_with(
        StackName='TestStack',
        ChangeSetName='TestChangeSet',
        WaiterConfig={'Delay': 5, 'MaxAttempts': 120}
    )
    create_complete_client.describe_change_set.assert_called_once_with(
        ChangeSetName='TestChangeSet',
        StackName='TestStack'
    )

    captured = capsys.readouterr()
    assert 'Stack: TestStack, Status: CREATE_COMPLETE' in captured.out
    assert 'Existing ChangeSets:\n  2020-01-01 00:00:00: ExistingChangeSet (CREATE_COMPLETE)' in captured.out
    assert 'Creating ChangeSet TestChangeSet' in captured.out
    assert 'Action    LogicalResourceId    ResourceType     Replacement' in captured.out
    assert 'Add       Queue                AWS::SQS::Queue  -' in captured.out
    assert 'ChangeSet TestChangeSet is ready to run' in captured.out


def test_deploy_no_changes(create_complete_client, config, capsys):
    # Configure waiter to throw WaiterError for FAILURE due to no changes
    waiter_error = WaiterError('change_set_create_complete',
                               'No Changes',
                               {'Status': 'FAILED', 'StatusReason': 'No updates are to be performed'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    create_complete_client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = Runner(create_complete_client, config)
    runner.deploy()

    create_complete_client.list_change_sets.assert_called_once_with(StackName='TestStack')
    create_complete_client.create_change_set.assert_called_once()
    create_complete_client.get_waiter.assert_called_once_with('change_set_create_complete')
    create_complete_client.describe_change_set.assert_not_called()

    captured = capsys.readouterr()
    assert 'No changes to Stack TestStack' in captured.out


def test_deploy_waiter_failed(create_complete_client, config):
    # Configure waiter to throw WaiterError for some unknown other reasons
    waiter_error = WaiterError('change_set_create_complete',
                               'No Changes',
                               {'Status': 'FAILED', 'StatusReason': 'Some other reason'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    create_complete_client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = Runner(create_complete_client, config)

    with pytest.raises(StackError, match='ChangeSet creation failed - Status: FAILED, Reason: Some other reason'):
        runner.deploy()


def test_execute_change_set(create_complete_client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    runner = Runner(create_complete_client, config)
    runner.execute_change_set()

    create_complete_client.describe_stack_events.assert_called_once_with(StackName='TestStack')
    create_complete_client.get_waiter.assert_called_once_with('stack_update_complete')
    create_complete_client.get_waiter().wait.assert_called_once_with(
        StackName='TestStack',
        WaiterConfig={'Delay': 10, 'MaxAttempts': 360}
    )
    create_complete_client.get_paginator.assert_called_once_with('describe_stack_events')
    create_complete_client.get_paginator().paginate.assert_called_once_with(StackName='TestStack')

    captured = capsys.readouterr()

    assert 'Executing ChangeSet TestChangeSet for TestStack' in captured.out
    assert 'ChangeSet TestChangeSet for TestStack successfully completed:' in captured.out
    assert 'Timestamp            LogicalResourceId    ResourceType                ResourceStatus      Reason' in captured.out
    assert '2020-01-01 13:23:11  TestStack            AWS::CloudFormation::Stack  UPDATE_IN_PROGRESS  User Initiated' in captured.out
    assert '2020-01-01 13:24:53  Queue                AWS::SQS::Queue             CREATE_COMPLETE     -' in captured.out
    assert '2020-01-01 13:25:01  TestStack            AWS::CloudFormation::Stack  UPDATE_COMPLETE     -' in captured.out

    # We shouldn't have the previous events in the output
    assert 'AWS::CloudFormation::Stack  CREATE_COMPLETE' not in captured.out
