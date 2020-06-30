import boto3
import uuid
from botocore.exceptions import ClientError, WaiterError
from stackmanager.config import Config
from stackmanager.messages import info, warn, error
from stackmanager.exceptions import StackError, ValidationError
from tabulate import tabulate


class Runner:
    """
    Encapsulates calls to CloudFormation client to create, update and delete stacks
    """

    def __init__(self, client, config, change_set_name, auto_approve):
        """
        Initialize new instance
        :param client: CloudFormation client
        :param Config config: Parsed configuration
        :param str change_set_name: ChangeSet name to use, if not set a guid will be generated
        :param bool auto_approve: Whether to auto-approve changes
        """
        self.client = client
        self.config = config
        self.change_set_name = change_set_name if change_set_name else 'c'+str(uuid.uuid4()).replace('-', '')
        self.auto_approve = auto_approve
        self.stack = self.load_stack()

    def load_stack(self):
        """
        Load Description of stack to determine if it exists and the current status
        :return: Matching stack of None
        """
        try:
            stacks = self.client.describe_stacks(StackName=self.config.stack_name)['Stacks']
            return stacks[0]
        except ClientError:
            return None

    def deploy(self):
        """
        Create a new Stack or update an existing Stack using a ChangeSet.
        This will wait for ChangeSet to be created and print the details,
        and if Auto-Approve is set, will then execute the ChangeSet and wait for that to complete.
        If there are no changes in the ChangeSet it will be automatically deleted.
        :raises StackError: If creating the ChangeSet or executing it fails
        """
        info(f'\nCreating ChangeSet {self.change_set_name}\n')
        try:
            self.client.create_change_set(**self.build_change_set_args())
            if self.wait_for_change_set():
                if self.auto_approve:
                    self.execute_change_set()
                else:
                    self.pending_change_set()
        except ClientError as ce:
            raise StackError(ce)

    def pending_change_set(self):
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
            status = resp["Status"]
            reason = resp["StatusReason"]

            # See SAM CLI: https://github.com/awslabs/aws-sam-cli/blob/develop/samcli/lib/deploy/deployer.py#L272
            if (
                    status == "FAILED"
                    and "The submitted information didn't contain changes." in reason
                    or "No updates are to be performed" in reason
            ):
                warn('No changes to Stack {}'.format(self.config.stack_name))
                self.client.delete_change_set(ChangeSetName=self.change_set_name, StackName=self.config.stack_name)
                return False

            raise StackError(we)

        describe_change_set_response = self.client.describe_change_set(ChangeSetName=self.change_set_name,
                                                                       StackName=self.config.stack_name)

        table = [[change['ResourceChange']['Action'],
                  change['ResourceChange']['LogicalResourceId'],
                  change['ResourceChange']['ResourceType'],
                  change['ResourceChange'].get('Replacement', '-')]
                 for change in describe_change_set_response['Changes']]
        print(tabulate(table, headers=['Action', 'LogicalResourceId', 'ResourceType', 'Replacement']))
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

            self.client.get_waiter('stack_update_complete' if self.stack else 'stack_create_complete').wait(
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 10, 'MaxAttempts': 360})

            info(f'\nChangeSet {self.change_set_name} for {self.config.stack_name} successfully completed:\n')
            self.print_events(last_timestamp)

        except ClientError as ce:
            raise StackError(ce)
        except WaiterError as we:
            error(f'\nChangeSet {self.change_set_name} for {self.config.stack_name} failed:\n')
            self.print_events(last_timestamp)
            raise StackError(we)

    def delete(self, retain_resources):
        """
        Delete a Stack, optionally retraining certain resources.
        Waits for Stack to delete and prints Events if deletion fails
        :param list retain_resources: List of LogicalIds to retain
        :raises StackError: if deletion fails
        """
        if not self.stack:
            raise ValidationError(f'Stack {self.config.stack_name} not found')

        info(f'\nDeleting Stack {self.config.stack_name}')
        last_timestamp = self.get_last_timestamp()

        try:
            self.client.delete_stack(StackName=self.config.stack_name, RetainResources=retain_resources)

            self.client.get_waiter('stack_delete_complete').wait(
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 10, 'MaxAttempts': 360})

            info(f'\nDeletion of Stack {self.config.stack_name} successfully completed')
        except ClientError as ce:
            raise StackError(ce)
        except WaiterError as we:
            error(f'\nDeletion of Stack {self.config.stack_name} failed:\n')
            self.print_events(last_timestamp)
            raise StackError(we)

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
        paginator = self.client.get_paginator("describe_stack_events")
        iterator = paginator.paginate(StackName=self.config.stack_name)
        table = []
        for page in iterator:
            for event in page['StackEvents']:
                if not last_timestamp or event['Timestamp'] > last_timestamp:
                    table.append([event['Timestamp'], event['LogicalResourceId'], event['ResourceType'],
                                 event['ResourceStatus'], event.get('ResourceStatusReason', '-')])

        table.reverse()
        print(tabulate(table, headers=['Timestamp', 'LogicalResourceId', 'ResourceType', 'ResourceStatus', 'Reason']))

    def build_change_set_args(self):
        """
        Build dictionary of arguments for creating a ChangeSet
        :return: Dictionary of arguments based upon Config
        """
        args = {
            'StackName': self.config.stack_name,
            'ChangeSetName': self.change_set_name,
            'ChangeSetType': 'UPDATE' if self.stack else 'CREATE',
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
        Converts Parameters dictionary into ParameterKey/ParameterValue pairs
        :return: Parameters dictionary
        """
        return [({'ParameterKey': k, 'ParameterValue': v}) for k, v in self.config.parameters.items()]

    def build_tags(self):
        """
        Converts Tags dictionary into Key/Value pairs
        :return: Tags dictionary
        """
        return [({'Key': k, 'Value': v}) for k, v in self.config.tags.items()]


def create_runner(profile, config, change_set_name, auto_approve):
    """
    Factory method for runner, responsible for creating boto3 client and picking appropriate Runner implementation.
    :param str profile: AWS Profile from command line
    :param Config config: Parsed Configuration
    :param str change_set_name: Name of ChangeSet to use
    :param bool auto_approve: Whether to auto-approve changes
    :return: Runner instance
    """
    session = boto3.Session(profile_name=profile, region_name=config.region)
    return Runner(session.client('cloudformation'), config, change_set_name, auto_approve)
