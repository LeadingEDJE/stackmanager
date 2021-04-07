import arrow
import boto3
import os
import uuid
from botocore.exceptions import ClientError, WaiterError
from stackmanager.config import Config, USE_PREVIOUS_VALUE
from stackmanager.exceptions import StackError, ValidationError
from stackmanager.messages import echo, info, warn, error, table
from stackmanager.status import StackStatus
from textwrap import wrap


class Runner:
    """
    Encapsulates calls to CloudFormation client to create, update and delete stacks
    """

    def __init__(self, client, config):
        """
        Initialize new instance
        :param client: CloudFormation client
        :param Config config: Parsed configuration
        """
        self.client = client
        self.config = config
        change_set_name = config.change_set_name
        self.change_set_name = change_set_name if change_set_name else 'c'+str(uuid.uuid4()).replace('-', '')
        self.stack = self.load_stack()

    def deploy(self):
        """
        Create a new Stack or update an existing Stack using a ChangeSet.
        This will wait for ChangeSet to be created and print the details,
        and if Auto-Approve is set, will then execute the ChangeSet and wait for that to complete.
        If there are no changes in the ChangeSet it will be automatically deleted.
        :raises StackError: If creating the ChangeSet or executing it fails
        :raises ValidationError: If stack is not in a deployable status
        """
        self.print_stack_status()

        if not StackStatus.is_creatable(self.stack) and not StackStatus.is_updatable(self.stack):
            stack_status = StackStatus.get_status(self.stack)
            if stack_status == StackStatus.ROLLBACK_COMPLETE:
                warn(f'Deleting Stack {self.config.stack_name} in ROLLBACK_COMPLETE status before attempting to create')
                self.delete()
            else:
                raise ValidationError(f'Stack {self.config.stack_name} is not in a deployable status: '
                                      f'{stack_status.name}')

        self.check_change_sets()

        info(f'\nCreating ChangeSet {self.change_set_name}\n')
        try:
            change_set_id = self.client.create_change_set(**self.build_change_set_args())['Id']
            if self.wait_for_change_set():
                if self.config.auto_apply:
                    self.execute_change_set()
                else:
                    self.pending_change_set(change_set_id)
            else:
                # Will update Termination protection if there are no other changes
                self.update_termination_protection()
        except ClientError as ce:
            raise StackError(ce)

    def apply_change_set(self):
        """
        Apply Change Set, first printing the current stack status.
        """
        self.print_stack_status()
        self.execute_change_set()

    def reject_change_set(self):
        """
        Delete the named ChangeSet, and if the stack is in the REVIEW_IN_PROGRESS status and there are
        no remaining ChangeSets, then delete the stack.
        """
        if not self.stack:
            raise ValidationError(f'Stack {self.config.stack_name} not found')

        self.print_stack_status()
        try:
            self.client.describe_change_set(ChangeSetName=self.change_set_name, StackName=self.config.stack_name)
        except self.client.exceptions.ChangeSetNotFoundException:
            raise ValidationError(f'ChangeSet {self.change_set_name} not found')

        info(f'\nDeleting ChangeSet {self.change_set_name} for {self.config.stack_name}')

        self.client.delete_change_set(ChangeSetName=self.change_set_name, StackName=self.config.stack_name)

        if StackStatus.is_status(self.stack, StackStatus.REVIEW_IN_PROGRESS):
            change_sets = self.client.list_change_sets(StackName=self.config.stack_name)['Summaries']
            if not change_sets:
                info(f'\nDeleting REVIEW_IN_PROGRESS Stack {self.config.stack_name} that has no remaining ChangeSets')
                # Delete stack, no need to wait for deletion to complete
                self.client.delete_stack(StackName=self.config.stack_name)

    def delete(self, retain_resources=[]):
        """
        Delete a Stack, optionally retraining certain resources.
        Waits for Stack to delete and prints Events if deletion fails
        :param list retain_resources: List of LogicalIds to retain
        :raises StackError: if deletion fails
        """
        if not self.stack:
            raise ValidationError(f'Stack {self.config.stack_name} not found')

        self.print_stack_status()

        if not StackStatus.is_deletable(self.stack):
            raise ValidationError(f'Stack {self.config.stack_name} is not in a deletable status: '
                                  f'{StackStatus.get_status(self.stack).name}')

        self.update_termination_protection(deleting=True)

        info(f'\nDeleting Stack {self.config.stack_name}')
        last_timestamp = self.get_last_timestamp()

        try:
            self.client.delete_stack(StackName=self.config.stack_name, RetainResources=retain_resources)

            self.client.get_waiter('stack_delete_complete').wait(
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 10, 'MaxAttempts': 360})

            info(f'\nDeletion of Stack {self.config.stack_name} successfully completed')
            self.stack = None
        except ClientError as ce:
            raise StackError(ce)
        except WaiterError as we:
            error(f'\nDeletion of Stack {self.config.stack_name} failed:\n')
            self.print_events(last_timestamp)
            raise StackError(we)

    def status(self, event_days):
        """
        Output the current status of the stack showing pending ChangeSets and recent events.
        :param int event_days: Number of days to show events for
        """
        self.print_stack_status()
        self.check_change_sets()

        if self.stack:
            last_timestamp = arrow.utcnow().shift(days=-event_days)
            info(f'\nEvents since {self.format_timestamp(last_timestamp)}:\n')
            self.print_events(last_timestamp.datetime)
            self.print_outputs()

    def get_output(self, output_key):
        """
        Return value of matching output, or throw exception
        :param str output_key: Output Key to return value for
        :return: Matching output value
        :raises ValidationError: If stack does not exist or matching output not found
        """
        if not self.stack:
            raise ValidationError(f'Stack {self.config.stack_name} not found')

        output_value = next((o['OutputValue'] for o in self.stack.get('Outputs', []) if o['OutputKey'] == output_key),
                            None)
        if output_value:
            return output_value
        raise ValidationError(f'Output {output_key} not found')

    def load_stack(self):
        """
        Load Description of stack to determine if it exists and the current status
        :return: Matching stack of None
        """
        try:
            stacks = self.client.describe_stacks(StackName=self.config.stack_name)['Stacks']
            stack = stacks[0]
            return stack
        except ClientError as ce:
            if ce.response['Error']['Code'] == 'ValidationError':
                return None
            else:
                raise StackError(ce)

    def print_stack_status(self):
        """
        Print the status of the stack if it exists or does not, with last update (or creation) timestamp.
        """
        if self.stack:
            stack_timestamp = self.stack['LastUpdatedTime'] if 'LastUpdatedTime' in self.stack \
                else self.stack['CreationTime']
            info(f'\nStack: {self.config.stack_name}, Status: {StackStatus.get_status(self.stack).name} '
                 f'({self.format_timestamp(stack_timestamp)})')
        else:
            info(f'\nStack: {self.config.stack_name}, Status: does not exist')

    def check_change_sets(self):
        """
        Check for existing change sets, and depending upon 'ExistingChanges' setting we may prevent the deployment
        :raises ValidationError: If ChangeSets exist and are not allowed
        """
        if self.stack:
            change_sets = self.client.list_change_sets(StackName=self.config.stack_name)['Summaries']
            change_sets.sort(key=lambda c: c['CreationTime'])
            successful_change_sets = [c for c in change_sets if c['Status'] in ['CREATE_PENDING', 'CREATE_IN_PROGRESS',
                                                                                'CREATE_COMPLETE']]

            if change_sets:
                echo('\nExisting ChangeSets:')
                for cs in change_sets:
                    echo(f'  {self.format_timestamp(cs["CreationTime"])}: {cs["ChangeSetName"]} ({cs["Status"]})')
                if self.config.existing_changes == 'DISALLOW':
                    raise ValidationError('Creation of new ChangeSet not allowed when existing ChangeSets found')
                elif self.config.existing_changes == 'FAILED_ONLY' and successful_change_sets:
                    raise ValidationError('Creation of new ChangeSet not allowed when existing valid ChangeSets found')

    def pending_change_set(self, change_set_id):
        """Subclasses can override this to export the change set information in another format"""
        info(f'\nChangeSet {self.change_set_name} is ready to run')

    def wait_for_change_set(self):
        """
        Wait for a ChangeSet to be created, printing the details when it is created.
        :return: True if ChangeSet created, False if there are no changes
        :raises StackError: If creation of ChangeSet fails for reason other than no changes
        """
        try:
            self.client.get_waiter('change_set_create_complete').wait(
                ChangeSetName=self.change_set_name,
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 5, 'MaxAttempts': 120})
        except WaiterError as we:
            resp = we.last_response
            status = resp['Status']
            reason = resp['StatusReason']

            # See SAM CLI: https://github.com/awslabs/aws-sam-cli/blob/develop/samcli/lib/deploy/deployer.py#L272
            if (
                    status == 'FAILED'
                    and "The submitted information didn't contain changes." in reason
                    or 'No updates are to be performed' in reason
            ):
                warn('No changes to Stack {}'.format(self.config.stack_name))
                self.client.delete_change_set(ChangeSetName=self.change_set_name, StackName=self.config.stack_name)
                return False

            raise StackError(f'ChangeSet creation failed - Status: {status}, Reason: {reason}')

        describe_change_set_response = self.client.describe_change_set(ChangeSetName=self.change_set_name,
                                                                       StackName=self.config.stack_name)

        data = [[change['ResourceChange']['Action'],
                 change['ResourceChange']['LogicalResourceId'],
                 change['ResourceChange']['ResourceType'],
                 change['ResourceChange'].get('Replacement', '-')]
                for change in describe_change_set_response['Changes']]
        table(data, ['Action', 'LogicalResourceId', 'ResourceType', 'Replacement'])
        return True

    def execute_change_set(self):
        """
        Execute a ChangeSet, waiting for execution to complete and printing the details of Stack Events
        caused by this ChangeSet
        :raises StackError: If there is an error executing the ChangeSet
        """
        last_timestamp = self.get_last_timestamp()

        try:
            info(f'\nExecuting ChangeSet {self.change_set_name} for {self.config.stack_name}')

            self.client.execute_change_set(ChangeSetName=self.change_set_name, StackName=self.config.stack_name)

            waiter_name = 'stack_create_complete' if StackStatus.is_creatable(self.stack) else 'stack_update_complete'
            self.client.get_waiter(waiter_name).wait(StackName=self.config.stack_name,
                                                     WaiterConfig={'Delay': 10, 'MaxAttempts': 360})

            info(f'\nChangeSet {self.change_set_name} for {self.config.stack_name} successfully completed:\n')
            self.print_events(last_timestamp)

            self.stack = self.load_stack()
            self.update_termination_protection()
            self.print_outputs()

        except ClientError as ce:
            raise StackError(ce)
        except WaiterError as we:
            self.failed_change_set(last_timestamp)
            raise StackError(we)

    def update_termination_protection(self, deleting=False):
        protect = False if deleting else self.config.termination_protection
        current = False if not self.stack else self.stack.get('EnableTerminationProtection', False)

        if protect is not current:
            self.client.update_termination_protection(StackName=self.config.stack_name,
                                                      EnableTerminationProtection=protect)
            info(f'\n{"Enabled" if protect else "Disabled"} Termination Protection')

    def failed_change_set(self, last_timestamp):
        """
        Print Stack Events on failed change set.
        Subclasses can override this to output errors in a different format.
        """
        error(f'\nChangeSet {self.change_set_name} for {self.config.stack_name} failed:\n')
        self.print_events(last_timestamp)

    def get_last_timestamp(self):
        """
        Get the last timestamp from the stack events, or None if there is no stack
        :return: Last timestamp or None
        """
        if self.stack:
            return self.client.describe_stack_events(StackName=self.config.stack_name)["StackEvents"][0]["Timestamp"]
        return None

    def print_events(self, last_timestamp):
        """
        Print events occurring since the last timestamp if provided
        :param str last_timestamp: Last Timestamp as UTC string
        """
        paginator = self.client.get_paginator('describe_stack_events')
        iterator = paginator.paginate(StackName=self.config.stack_name)
        data = []
        for page in iterator:
            for event in page['StackEvents']:
                if not last_timestamp or event['Timestamp'] > last_timestamp:
                    reason = '\n'.join(wrap(event.get('ResourceStatusReason', '-'), 50))
                    data.append([self.format_timestamp(event['Timestamp']), event['LogicalResourceId'],
                                event['ResourceType'], event['ResourceStatus'], reason])

        if data:
            data.reverse()
            table(data, ['Timestamp', 'LogicalResourceId', 'ResourceType', 'ResourceStatus', 'Reason'])
        else:
            warn('No events')

    def print_outputs(self):
        if self.stack and 'Outputs' in self.stack:
            info('\nOutputs:\n')
            data = [[o['OutputKey'], o['OutputValue']] for o in self.stack['Outputs']]
            table(data, ['Key', 'Value'])

    def build_change_set_args(self):
        """
        Build dictionary of arguments for creating a ChangeSet
        :return: Dictionary of arguments based upon Config
        """
        args = {
            'StackName': self.config.stack_name,
            'ChangeSetName': self.change_set_name,
            'ChangeSetType': 'CREATE' if StackStatus.is_creatable(self.stack) else 'UPDATE',
            'Parameters': self.build_parameters(),
            'Tags': self.build_tags()
        }
        if self.config.capabilities:
            args['Capabilities'] = self.config.capabilities

        if Config.is_template_url(self.config.template):
            args['TemplateURL'] = self.config.template
        else:
            with open(self.config.template) as t:
                args['TemplateBody'] = t.read()

        return args

    def build_parameters(self):
        """
        Converts Parameters dictionary into ParameterKey/ParameterValue pairs.
        Supports UsePreviousValue if value is <<UsePreviousValue>> constant,
        :return: Parameters dictionary
        """
        return [{'ParameterKey': k, 'UsePreviousValue': True}
                if v == USE_PREVIOUS_VALUE else
                {'ParameterKey': k, 'ParameterValue': v}
                for k, v in self.config.parameters.items()]

    def build_tags(self):
        """
        Converts Tags dictionary into Key/Value pairs
        :return: Tags dictionary
        """
        return [{'Key': k, 'Value': v} for k, v in self.config.tags.items()]

    def format_timestamp(self, timestamp):
        """
        Format Timestamp in local or specified timezone.
        :param timestamp: Raw UTC timestamp from AWS
        :return: Formatted timestamp
        """
        if 'STACKMANAGER_TIMEZONE' in os.environ:
            # Skip timezone offset if using provided timezone
            return arrow.get(timestamp).to(os.environ['STACKMANAGER_TIMEZONE']).format('YYYY-MM-DD HH:mm:ss')

        return arrow.get(timestamp).to('local').format()


class AzureDevOpsRunner(Runner):
    """
    Subclass of Runner with extra functionality for Azure DevOps
    """

    def wait_for_change_set(self):
        """
        Override to log a result of SucceededWithIssues if no changes in ChangeSet
        :return: True if change set created, False if no changes
        """
        if super().wait_for_change_set():
            return True

        print(f'##vso[task.logissue type=warning]{self.config.stack_name} '
              f'({self.config.environment}/{self.config.region}) - No Changes found in ChangeSet')
        print('##vso[task.complete result=SucceededWithIssues]DONE')
        return False

    def pending_change_set(self, change_set_id):
        """
        Set Azure DevOps variables for ChangeSet Name and ChangeSet Id.
        ChangeSetName variable defaults to change_set_name, but can be overridden using CHANGE_SET_NAME_VARIABLE.
        ChangeSetId variable defaults to change_set_id, but can be overridden using CHANGE_SET_ID_VARIABLE.
        """
        super().pending_change_set(change_set_id)

        change_set_name_variable = os.environ.get('CHANGE_SET_NAME_VARIABLE', 'change_set_name')
        change_set_id_variable = os.environ.get('CHANGE_SET_ID_VARIABLE', 'change_set_id')
        print(f'##vso[task.setvariable variable={change_set_name_variable};isOutput=true]{self.change_set_name}')
        print(f'##vso[task.setvariable variable={change_set_id_variable};isOutput=true]{change_set_id}')

    def failed_change_set(self, last_timestamp):
        """
        Override to log a task issue that the ChangeSet failed
        :param str last_timestamp: Timestamp of last change
        """
        super().failed_change_set(last_timestamp)

        print(f'##vso[task.logissue type=error]{self.config.stack_name} '
              f'({self.config.environment}/{self.config.region}) - ChangeSet {self.change_set_name} failed')


def create_runner(profile, config):
    """
    Factory method for runner, responsible for creating boto3 client and picking appropriate Runner implementation.
    :param str profile: AWS Profile from command line
    :param Config config: Parsed Configuration
    :return: Runner instance
    """
    session = boto3.Session(profile_name=profile, region_name=config.region)
    client = session.client('cloudformation')
    azure_devops = 'SYSTEM_TEAMPROJECTID' in os.environ
    if azure_devops:
        return AzureDevOpsRunner(client, config)
    else:
        return Runner(client, config)


def create_changeset_runner(profile, region, change_set_id):
    """
    Create a runner for processing a changeset using it's id.
    This first describes the changeset to get the stack name, and then the runner can be created with a dummy config.
    :param profile: AWS Profile from command line
    :param region: AWS Region from command line
    :param change_set_id: Change Set identifier
    :return: Runner instance
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client('cloudformation')
    try:
        change_set = client.describe_change_set(ChangeSetName=change_set_id)
        config = Config({
            'Environment': 'unknown',
            'Region': session.region_name,
            'StackName': change_set['StackName'],
            'ChangeSetName': change_set['ChangeSetName']
        })
        return create_runner(profile, config)

    except client.exceptions.ChangeSetNotFoundException:
        raise ValidationError(f'ChangeSet {change_set_id} not found')
