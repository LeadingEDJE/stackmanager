import os
import pytest
from botocore.exceptions import ClientError, WaiterError
from stackmanager.config import Config
from stackmanager.exceptions import StackError, ValidationError
from stackmanager.runner import AzureDevOpsRunner, Runner
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
def client(create_complete_stack, single_successful_changeset, describe_changeset, before_and_after_events):
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


###################################################
# Runner tests
###################################################

def test_load_stack(client, config, capsys):
    runner = Runner(client, config)

    client.describe_stacks.assert_called_once_with(StackName='TestStack')
    assert runner.stack is not None
    assert runner.change_set_name == 'TestChangeSet'

    captured = capsys.readouterr()
    assert captured.out == '\nStack: TestStack, Status: CREATE_COMPLETE\n'


def test_load_stack_does_not_exist(config, capsys):
    attrs = {'describe_stacks.side_effect': ClientError({}, 'describe_stacks')}
    mock = MagicMock(**attrs)
    runner = Runner(mock, config)

    mock.describe_stacks.assert_called_once_with(StackName='TestStack')
    assert runner.stack is None
    assert runner.change_set_name == 'TestChangeSet'

    captured = capsys.readouterr()
    assert captured.out == '\nStack: TestStack, Status: does not exist\n'


def test_deploy_rollback_complete(client, config):
    describe_stacks = {
        'Stacks': [{
            'StackName': 'TestStack',
            'StackStatus': StackStatus.ROLLBACK_COMPLETE.name
        }]
    }
    client.configure_mock(**{'describe_stacks.return_value': describe_stacks})

    runner = Runner(client, config)
    runner.deploy()

    client.delete_stack.assert_called_once_with(StackName='TestStack', RetainResources=[])


def test_deploy_invalid_status(client, config):
    describe_stacks = {
        'Stacks': [{
            'StackName': 'TestStack',
            'StackStatus': StackStatus.UPDATE_IN_PROGRESS.name
        }]
    }
    client.configure_mock(**{'describe_stacks.return_value': describe_stacks})

    runner = Runner(client, config)
    with pytest.raises(ValidationError, match='Stack TestStack is not in a deployable status: UPDATE_IN_PROGRESS'):
        runner.deploy()


def test_deploy_disallow_existing_changes(client, config):
    config.config['ExistingChanges'] = 'DISALLOW'

    runner = Runner(client, config)
    with pytest.raises(ValidationError, match='Creation of new ChangeSet not allowed when existing ChangeSets found'):
        runner.deploy()

    client.list_change_sets.assert_called_once_with(StackName='TestStack')


def test_deploy_failed_only_existing_changes(client, config):
    config.config['ExistingChanges'] = 'FAILED_ONLY'

    runner = Runner(client, config)
    with pytest.raises(ValidationError,
                       match='Creation of new ChangeSet not allowed when existing valid ChangeSets found'):
        runner.deploy()

    client.list_change_sets.assert_called_once_with(StackName='TestStack')


def test_deploy(client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    runner = Runner(client, config)
    runner.deploy()

    client.list_change_sets.assert_called_once_with(StackName='TestStack')
    client.create_change_set.assert_called_once_with(
        StackName='TestStack',
        ChangeSetName='TestChangeSet',
        ChangeSetType='UPDATE',
        Parameters=[{'ParameterKey': 'Param1', 'ParameterValue': 'Value1'}],
        Tags=[{'Key': 'Tag1', 'Value': 'Value1'}],
        Capabilities=['CAPABILITY_IAM'],
        TemplateBody='AWSTemplateFormatVersion : "2010-09-09"'
    )
    client.get_waiter.assert_called_once_with('change_set_create_complete')
    client.get_waiter().wait.assert_called_once_with(
        StackName='TestStack',
        ChangeSetName='TestChangeSet',
        WaiterConfig={'Delay': 5, 'MaxAttempts': 120}
    )
    client.describe_change_set.assert_called_once_with(ChangeSetName='TestChangeSet', StackName='TestStack')

    captured = capsys.readouterr()
    assert 'Stack: TestStack, Status: CREATE_COMPLETE' in captured.out
    assert 'Existing ChangeSets:\n  2020-01-01 00:00:00: ExistingChangeSet (CREATE_COMPLETE)' in captured.out
    assert 'Creating ChangeSet TestChangeSet' in captured.out
    assert 'Action    LogicalResourceId    ResourceType     Replacement' in captured.out
    assert 'Add       Queue                AWS::SQS::Queue  -' in captured.out
    assert 'ChangeSet TestChangeSet is ready to run' in captured.out


def test_deploy_no_changes(client, config, capsys):
    # Configure waiter to throw WaiterError for FAILURE due to no changes
    waiter_error = WaiterError('change_set_create_complete',
                               'No Changes',
                               {'Status': 'FAILED', 'StatusReason': 'No updates are to be performed'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = Runner(client, config)
    runner.deploy()

    client.list_change_sets.assert_called_once_with(StackName='TestStack')
    client.create_change_set.assert_called_once()
    client.get_waiter.assert_called_once_with('change_set_create_complete')
    client.describe_change_set.assert_not_called()

    captured = capsys.readouterr()
    assert 'No changes to Stack TestStack' in captured.out


def test_deploy_client_error(client, config):
    client.configure_mock(**{'create_change_set.side_effect': ClientError({}, 'create_change_set')})
    runner = Runner(client, config)
    with pytest.raises(StackError, match='An error occurred \\(Unknown\\) when calling the create_change_set .*'):
        runner.deploy()


def test_deploy_waiter_failed(client, config):
    # Configure waiter to throw WaiterError for some unknown other reasons
    waiter_error = WaiterError('change_set_create_complete',
                               'Other reason',
                               {'Status': 'FAILED', 'StatusReason': 'Some other reason'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = Runner(client, config)

    with pytest.raises(StackError, match='ChangeSet creation failed - Status: FAILED, Reason: Some other reason'):
        runner.deploy()


def test_execute_change_set(client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    runner = Runner(client, config)
    runner.execute_change_set()

    client.describe_stack_events.assert_called_once_with(StackName='TestStack')
    client.get_waiter.assert_called_once_with('stack_update_complete')
    client.get_waiter().wait.assert_called_once_with(
        StackName='TestStack',
        WaiterConfig={'Delay': 10, 'MaxAttempts': 360}
    )
    client.get_paginator.assert_called_once_with('describe_stack_events')
    client.get_paginator().paginate.assert_called_once_with(StackName='TestStack')

    captured = capsys.readouterr()

    assert 'Executing ChangeSet TestChangeSet for TestStack' in captured.out
    assert 'ChangeSet TestChangeSet for TestStack successfully completed:' in captured.out
    assert 'Timestamp            LogicalResourceId    ResourceType                ResourceStatus      Reason' in captured.out
    assert '2020-01-01 13:23:11  TestStack            AWS::CloudFormation::Stack  UPDATE_IN_PROGRESS  User Initiated' in captured.out
    assert '2020-01-01 13:24:53  Queue                AWS::SQS::Queue             CREATE_COMPLETE     -' in captured.out
    assert '2020-01-01 13:25:01  TestStack            AWS::CloudFormation::Stack  UPDATE_COMPLETE     -' in captured.out

    # We shouldn't have the previous events in the output
    assert 'AWS::CloudFormation::Stack  CREATE_COMPLETE' not in captured.out


def test_execute_change_set_client_error(client, config):
    client.configure_mock(**{'execute_change_set.side_effect': ClientError({}, 'execute_change_set')})
    runner = Runner(client, config)
    with pytest.raises(StackError, match='An error occurred \\(Unknown\\) when calling the execute_change_set .*'):
        runner.execute_change_set()


def test_execute_change_set_waiter_error(client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    # Configure waiter to throw WaiterError
    waiter_error = WaiterError('stack_update_complete',
                               'Update Failed',
                               {'Status': 'FAILED', 'StatusReason': 'Some reason'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})

    # Override Stack events
    stack_events = {
        'StackEvents': [
            {
                'Timestamp': '2020-01-01T13:33:41.00000-0000',
                'LogicalResourceId': 'Queue',
                'ResourceType': 'AWS::SQS::Queue',
                'ResourceStatus': 'CREATE_FAILED',
                'ResourceStatusReason': 'Something went wrong'
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
    paginator_mock = MagicMock(**{'paginate.return_value': [stack_events]})

    client.configure_mock(**{
        'get_waiter.return_value': waiter_mock,
        'get_paginator.return_value': paginator_mock
    })

    runner = Runner(client, config)
    with pytest.raises(StackError, match='Waiter stack_update_complete failed: Update Failed'):
        runner.execute_change_set()

    captured = capsys.readouterr()
    assert 'ChangeSet TestChangeSet for TestStack failed:' in captured.out
    assert '2020-01-01 13:33:41  Queue                AWS::SQS::Queue  CREATE_FAILED     Something went wrong' \
           in captured.out


def test_reject(client, config, capsys):
    runner = Runner(client, config)
    runner.reject_change_set()

    client.describe_change_set.assert_called_once_with(StackName='TestStack', ChangeSetName='TestChangeSet')
    client.delete_change_set.assert_called_once_with(StackName='TestStack', ChangeSetName='TestChangeSet')

    captured = capsys.readouterr()
    assert 'Deleting ChangeSet TestChangeSet for TestStack' in captured.out


def test_reject_delete_stack(client, config, capsys):
    # return no changesets
    client.configure_mock(**{'list_change_sets.return_value': {'Summaries': []}})

    runner = Runner(client, config)
    # Update the status
    runner.stack['StackStatus'] = StackStatus.REVIEW_IN_PROGRESS.name

    runner.reject_change_set()

    client.describe_change_set.assert_called_once_with(StackName='TestStack', ChangeSetName='TestChangeSet')
    client.delete_change_set.assert_called_once_with(StackName='TestStack', ChangeSetName='TestChangeSet')
    client.list_change_sets.assert_called_once_with(StackName='TestStack')
    client.delete_stack.assert_called_once_with(StackName='TestStack')

    captured = capsys.readouterr()
    assert 'Deleting REVIEW_IN_PROGRESS Stack TestStack that has no remaining ChangeSets' in captured.out


def test_reject_no_stack(config):
    attrs = {'describe_stacks.side_effect': ClientError({}, 'describe_stacks')}
    mock = MagicMock(**attrs)
    runner = Runner(mock, config)

    with pytest.raises(ValidationError, match='Stack TestStack not found'):
        runner.reject_change_set()


def test_delete(client, config, capsys):
    runner = Runner(client, config)
    runner.delete()

    assert runner.stack is None

    client.describe_stack_events.assert_called_once_with(StackName='TestStack')
    client.delete_stack.assert_called_once_with(StackName='TestStack', RetainResources=[])
    client.get_waiter.assert_called_once_with('stack_delete_complete')
    client.get_waiter().wait.assert_called_once_with(
        StackName='TestStack',
        WaiterConfig={'Delay': 10, 'MaxAttempts': 360}
    )


def test_delete_no_stack(config):
    attrs = {'describe_stacks.side_effect': ClientError({}, 'describe_stacks')}
    mock = MagicMock(**attrs)
    runner = Runner(mock, config)

    with pytest.raises(ValidationError, match='Stack TestStack not found'):
        runner.delete()


def test_delete_invalid_status(client, config):
    describe_stacks = {
        'Stacks': [{
            'StackName': 'TestStack',
            'StackStatus': StackStatus.UPDATE_IN_PROGRESS.name
        }]
    }
    client.configure_mock(**{'describe_stacks.return_value': describe_stacks})

    runner = Runner(client, config)

    with pytest.raises(ValidationError, match='Stack TestStack is not in a deletable status: UPDATE_IN_PROGRESS'):
        runner.delete()


def test_delete_client_error(client, config):
    client.configure_mock(**{'delete_stack.side_effect': ClientError({}, 'delete_stack')})
    runner = Runner(client, config)
    with pytest.raises(StackError, match='An error occurred \\(Unknown\\) when calling the delete_stack operation.*'):
        runner.delete()


def test_delete_waiter_error(client, config, capsys, monkeypatch):
    # Prevent differences in format depending upon where this runs
    monkeypatch.setenv('STACKMANAGER_TIMEZONE', 'UTC')

    # Configure waiter
    waiter_error = WaiterError('stack_delete_complete',
                               'Delete Failed',
                               {'Status': 'FAILED', 'StatusReason': 'Delete failed'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})

    # Override Stack events
    stack_events = {
        'StackEvents': [
            {
                'Timestamp': '2020-01-01T13:35:11.00000-0000',
                'LogicalResourceId': 'Topic',
                'ResourceType': 'AWS::SNS::Topic',
                'ResourceStatus': 'DELETE_FAILED',
                'ResourceStatusReason': 'Something went wrong'
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
    paginator_mock = MagicMock(**{'paginate.return_value': [stack_events]})

    client.configure_mock(**{
        'get_waiter.return_value': waiter_mock,
        'get_paginator.return_value': paginator_mock
    })

    runner = Runner(client, config)
    with pytest.raises(StackError, match='Waiter stack_delete_complete failed: Delete Failed'):
        runner.delete()

    captured = capsys.readouterr()
    assert 'Deletion of Stack TestStack failed:' in captured.out
    assert '2020-01-01 13:35:11  Topic                AWS::SNS::Topic  DELETE_FAILED     Something went wrong' \
           in captured.out


###################################################
# AzureDevOpsRunner tests
###################################################

def test_az_deploy_pending_changes(client, config, capsys):
    runner = AzureDevOpsRunner(client, config)
    runner.deploy()

    captured = capsys.readouterr()
    assert '##vso[task.setvariable variable=change_set_name;isOutput=true]TestChangeSet' in captured.out
    assert '##vso[task.setvariable variable=change_set_id;isOutput=true]TestChangeSetId' in captured.out


def test_az_deploy_pending_changes_variable_names(client, config, capsys, monkeypatch):
    monkeypatch.setenv('CHANGE_SET_NAME_VARIABLE', 'csn')
    monkeypatch.setenv('CHANGE_SET_ID_VARIABLE', 'csi')

    runner = AzureDevOpsRunner(client, config)
    runner.deploy()

    captured = capsys.readouterr()
    assert '##vso[task.setvariable variable=csn;isOutput=true]TestChangeSet' in captured.out
    assert '##vso[task.setvariable variable=csi;isOutput=true]TestChangeSetId' in captured.out


def test_az_deploy_no_changes(client, config, capsys):
    # Configure waiter to throw WaiterError for FAILURE due to no changes
    waiter_error = WaiterError('change_set_create_complete',
                               'No Changes',
                               {'Status': 'FAILED', 'StatusReason': 'No updates are to be performed'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = AzureDevOpsRunner(client, config)
    runner.deploy()

    captured = capsys.readouterr()
    assert '##vso[task.logissue type=warning]TestStack (test/us-east-1) - No Changes found in ChangeSet' in captured.out
    assert '##vso[task.complete result=SucceededWithIssues]DONE' in captured.out


def test_az_execute_change_set_waiter_error(client, config, capsys):
    # Configure waiter to throw WaiterError
    waiter_error = WaiterError('stack_update_complete',
                               'Update Failed',
                               {'Status': 'FAILED', 'StatusReason': 'Some reason'})
    waiter_mock = MagicMock(**{'wait.side_effect': waiter_error})
    client.configure_mock(**{'get_waiter.return_value': waiter_mock})

    runner = AzureDevOpsRunner(client, config)
    with pytest.raises(StackError, match='Waiter stack_update_complete failed: Update Failed'):
        runner.execute_change_set()

    captured = capsys.readouterr()
    assert '##vso[task.logissue type=error]TestStack (test/us-east-1) - ChangeSet TestChangeSet failed' in captured.out