import boto3
import uuid
from botocore.exceptions import ClientError, WaiterError
from stackmanager.config import Config
from stackmanager.messages import info, warn, error
from stackmanager.exceptions import StackError, ValidationError
from tabulate import tabulate


class Runner:

    def __init__(self, client, config, change_set_name, auto_approve):
        self.client = client
        self.config = config
        self.change_set_name = change_set_name if change_set_name else 'c'+str(uuid.uuid4()).replace('-', '')
        self.auto_approve = auto_approve
        self.stack = self.load_stack()

    def load_stack(self):
        try:
            stacks = self.client.describe_stacks(StackName=self.config.stack_name)['Stacks']
            return stacks[0]
        except ClientError:
            return None

    def deploy(self):
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
        if self.stack:
            return self.client.describe_stack_events(StackName=self.config.stack_name)["StackEvents"][0]["Timestamp"]
        return None

    def print_events(self, last_timestamp):
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
        """Converts Parameters dictionary into ParameterKey/ParameterValue pairs"""
        return [({'ParameterKey': k, 'ParameterValue': v}) for k, v in self.config.parameters.items()]

    def build_tags(self):
        """Converts Tags dictionary into Key/Value pairs"""
        return [({'Key': k, 'Value': v}) for k, v in self.config.tags.items()]


def create_runner(profile, config, change_set_name, auto_approve):
    session = boto3.Session(profile_name=profile, region_name=config.region)
    return Runner(session.client('cloudformation'), config, change_set_name, auto_approve)
