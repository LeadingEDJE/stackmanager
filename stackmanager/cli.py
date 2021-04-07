#!/usr/bin/env python
import click
import logging
import stackmanager.packager
from functools import update_wrapper
from stackmanager.config import Config
from stackmanager.exceptions import PackagingError, StackError, TransferError, ValidationError
from stackmanager.loader import load_config
from stackmanager.messages import echo, error
from stackmanager.runner import create_runner, create_changeset_runner
from stackmanager.uploader import create_uploader


logging.basicConfig(level=logging.WARN, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


class Context:
    """
    Click Context object that stores argument config, profile and Lambda zip file path
    """
    def __init__(self, profile, region):
        self.config = Config({})
        self.config.region = region
        self.profile = profile
        self.zip_file = None


def pass_merged_context(f):
    """
    Decorator function similar to @click.pass_context, but also merges region/profile options
    into the context and populates the option from the context.
    :param f: Function to decorate
    :return: Updated wrapper
    """
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        if 'region' in kwargs:
            if kwargs.get('region'):
                ctx.obj.config.region = kwargs.get('region')
            kwargs['region'] = ctx.obj.config.region
        if 'profile' in kwargs:
            if kwargs.get('profile'):
                ctx.obj.profile = kwargs.get('profile')
            kwargs['profile'] = ctx.obj.profile
        return ctx.invoke(f, ctx, *args, **kwargs)
    return update_wrapper(new_func, f)


def require_region(ctx, param, value):
    """
    Require region to be set in parameter or in context
    :param ctx: Context
    :param param: Click Parameter
    :param value: Parameter value
    :return: Parameter value
    """
    if not value and not ctx.obj.config.region:
        raise click.BadParameter(f'{param.name} is required for {ctx.command.name}')
    return value


@click.group(chain=True)
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-r', '--region', help='AWS Region to deploy')
def cli(ctx, profile, region):
    """
    Utility for managing CloudFormation stacks.
    """
    ctx.obj = Context(profile, region)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', callback=require_region, help='AWS Region to deploy')
@click.option('-t', '--template', help='Override template')
@click.option('--parameter', nargs=2, multiple=True, help='Override a parameter, can be specified multiple times')
@click.option('--parameter-use-previous', multiple=True, help='Use previous value for a parameter, can be specified multiple times')
@click.option('--change-set-name', help='Custom ChangeSet name')
@click.option('--existing-changes', type=click.Choice(['ALLOW', 'FAILED_ONLY', 'DISALLOW'], case_sensitive=False),
              default='ALLOW', help='Whether deployment is allowed when there are existing ChangeSets')
@click.option('--auto-apply', is_flag=True, help='Automatically apply created ChangeSet')
def deploy(ctx, profile, config_file, environment, region, template, parameter, parameter_use_previous, change_set_name,
           existing_changes, auto_apply):
    """
    Create or update a CloudFormation stack using ChangeSets.
    """
    try:
        cfg = load_config(config_file, ctx.obj.config, environment, Template=template, Parameters=parameter,
                          PreviousParameters=parameter_use_previous, ChangeSetName=change_set_name,
                          ExistingChanges=existing_changes, AutoApply=auto_apply)
        runner = create_runner(profile, cfg)
        runner.deploy()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', help='YAML Configuration file')
@click.option('-e', '--environment', help='Environment to deploy')
@click.option('-r', '--region', help='AWS Region to deploy')
@click.option('--change-set-name', help='Name of ChangeSet to apply')
@click.option('--change-set-id', help='Identifier of ChangeSet to apply')
def apply(ctx, profile, config_file, environment, region, change_set_name, change_set_id):
    """
    Apply a CloudFormation ChangeSet to create or update a CloudFormation stack.
    If using --change-set-name then --config --environment and --region are required.
    If using --change-set-id no other values are required (although --profile and --region may be needed).
    """
    if not change_set_name and not change_set_id:
        raise click.UsageError("Option '--change-set-name' or '--change-set-id' required.")

    try:
        if change_set_id:
            runner = create_changeset_runner(profile, region, change_set_id)
            runner.apply_change_set()
        else:
            if not config_file:
                raise click.UsageError("Missing option '-c' / '--config-file'.")
            if not environment:
                raise click.UsageError("Missing option '-e' / '--environment'.")

            cfg = load_config(config_file, ctx.obj.config, environment, False, ChangeSetName=change_set_name)
            runner = create_runner(profile, cfg)
            runner.apply_change_set()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', help='YAML Configuration file')
@click.option('-e', '--environment', help='Environment for stack')
@click.option('-r', '--region', help='AWS Region for stack')
@click.option('--change-set-name', help='Name of ChangeSet to reject')
@click.option('--change-set-id', help='Identifier of ChangeSet to reject')
def reject(ctx, profile, config_file, environment, region, change_set_name, change_set_id):
    """
    Reject a CloudFormation ChangeSet, deleting the stack if in REVIEW_IN_PROGRESS status and has no other ChangeSets.
    If using --change-set-name then --config --environment and --region are required.
    If using --change-set-id no other values are required (although --profile and --region may be needed).
    """
    if not change_set_name and not change_set_id:
        raise click.UsageError("Option '--change-set-name' or '--change-set-id' required.")

    try:
        if change_set_id:
            runner = create_changeset_runner(profile, region, change_set_id)
            runner.reject_change_set()
        else:
            if not config_file:
                raise click.UsageError("Missing option '-c' / '--config-file'.")
            if not environment:
                raise click.UsageError("Missing option '-e' / '--environment'.")

            cfg = load_config(config_file, ctx.obj.config, environment, False, ChangeSetName=change_set_name)
            runner = create_runner(profile, cfg)
            runner.reject_change_set()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', callback=require_region, help='AWS Region to deploy')
@click.option('--retain-resources', multiple=True, help='Logical Ids of resources to retain')
@click.confirmation_option('-Y', '--yes', prompt='Delete CloudFormation Stack?')
def delete(ctx, profile, config_file, environment, region, retain_resources):
    """
    Delete a CloudFormation stack.
    """
    try:
        cfg = load_config(config_file, ctx.obj.config, environment, False)
        runner = create_runner(profile, cfg)
        runner.delete(retain_resources)
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', callback=require_region, help='AWS Region to deploy')
@click.option('--event-days', type=int, default=7, help='Number of days of events to include in output')
def status(ctx, profile, config_file, environment, region, event_days):
    """
    Print current status of Stack.
    Includes pending ChangeSets and recent events.
    """
    try:
        cfg = load_config(config_file, ctx.obj.config, environment, False)
        runner = create_runner(profile, cfg)
        runner.status(event_days)
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config-file', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', callback=require_region, help='AWS Region to deploy')
@click.option('-o', '--output-key', required=True, help='Output Key')
def get_output(ctx, profile, config_file, environment, region, output_key):
    """
    Returns matching Output value if it exists.
    """
    try:
        cfg = load_config(config_file, ctx.obj.config, environment, False)
        runner = create_runner(profile, cfg)
        output_value = runner.get_output(output_key)
        echo(output_value)
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command(name='build-lambda')
@pass_merged_context
@click.option('-s', '--source-dir', required=True, help='Source directory')
@click.option('-o', '--output-dir', required=True, help='Output directory')
@click.option('--runtime', required=True, help='Lambda Runtime')
@click.option('--archive-name', help='Override archive name (defaults to source directory name)')
def build_lambda(ctx, source_dir, output_dir, runtime, archive_name):
    """
    Build a Lambda function zip file.
    Can be chained into the upload command where it pre-populates the --filename option.
    """
    try:
        ctx.obj.zip_file = stackmanager.packager.build_lambda(source_dir, output_dir, runtime, archive_name)
    except (PackagingError, ValidationError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@pass_merged_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-r', '--region', callback=require_region, help='AWS Region to upload to')
@click.option('-f', '--filename', help='File to upload')
@click.option('-b', '--bucket', required=True, help='Bucket to upload to')
@click.option('-k', '--key', required=True, help='Key to upload to')
@click.option('--bucket-parameter', default='LambdaBucket', help='CloudFormation parameter for Bucket')
@click.option('--key-parameter', default='LambdaKey', help='CloudFormation parameter for Key')
def upload(ctx, profile, region, filename, bucket, key, bucket_parameter, key_parameter):
    """
    Uploads a File to S3.
    This might be a large CloudFormation template, or a Lambda zip file.
    Can be chained into the deploy command where it pre-populates parameters for the uploaded file.
    """
    if not filename and not ctx.obj.zip_file:
        raise click.UsageError("Missing option '-f' / '--filename'.")

    try:
        uploader = create_uploader(profile, region)
        uploader.upload(filename or ctx.obj.zip_file, bucket, key)
        ctx.obj.config.add_parameters({
            bucket_parameter: bucket,
            key_parameter: key
        })
    except (TransferError, ValidationError) as e:
        error(f'\nError: {e}')
        exit(1)


if __name__ == '__main__':
    cli(prog_name='stackmanager')
