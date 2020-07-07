#!/usr/bin/env python
import click
import stackmanager.packager
from stackmanager.exceptions import PackagingError, StackError, TransferError, ValidationError
from stackmanager.loader import load_config
from stackmanager.messages import error
from stackmanager.runner import create_runner
from stackmanager.uploader import create_uploader


@click.group(chain=True)
@click.pass_context
def cli(ctx):
    """
    Utility for managing CloudFormation stacks.
    """
    ctx.obj = dict()


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('-t', '--template', help='Override template')
@click.option('--parameter', nargs=2, multiple=True, help='Override a parameter, can be specified multiple times')
@click.option('--change-set-name', help='Custom ChangeSet name')
@click.option('--auto-apply', is_flag=True, help='Automatically apply created ChangeSet')
def deploy(ctx, profile, config, environment, region, template, parameter, change_set_name, auto_apply):
    """
    Create or update a CloudFormation stack using ChangeSets.
    """
    try:
        cfg = load_config(config, environment, region, template, parameter)
        runner = create_runner(profile, cfg, change_set_name, auto_apply)
        runner.deploy()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('--change-set-name', required=True, help='ChangeSet to apply')
def apply(ctx, profile, config, environment, region, change_set_name):
    """
    Apply a CloudFormation ChangeSet to create or update a CloudFormation stack.
    """
    try:
        cfg = load_config(config, environment, region, None, None, False)
        runner = create_runner(profile, cfg, change_set_name, False)
        runner.execute_change_set()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('--retain-resources', multiple=True, help='Logical Ids of resources to retain')
def delete(ctx, profile, config, environment, region, retain_resources):
    """
    Delete a CloudFormation stack.
    """
    try:
        cfg = load_config(config, environment, region, None, None, False)
        runner = create_runner(profile, cfg, None, False)
        runner.delete(retain_resources)
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command(name='build-lambda')
@click.pass_context
@click.option('-s', '--source-dir', required=True, help='Source directory')
@click.option('-o', '--output-dir', required=True, help='Output directory')
@click.option('--runtime', required=True, help='Lambda Runtime')
@click.option('--archive-name', help='Override archive name (defaults to source directory name)')
def build_lambda(ctx, source_dir, output_dir, runtime, archive_name):
    """Build a Lambda function zip file."""
    try:
        stackmanager.packager.build_lambda(source_dir, output_dir, runtime, archive_name)
    except (PackagingError, ValidationError) as e:
        error(f'\nError: {e}')
        exit(1)


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-r', '--region', required=True, help='AWS Region to upload to')
@click.option('-f', '--filename', required=True, help='File to upload')
@click.option('-b', '--bucket', required=True, help='Bucket to upload to')
@click.option('-k', '--key', required=True, help='Key to upload to')
def upload(ctx, profile, region, filename, bucket, key):
    """
    Uploads a File to S3.
    This might be a large CloudFormation template, or a Lambda zip file.
    """
    try:
        uploader = create_uploader(profile, region)
        uploader.upload(filename, bucket, key)
    except (TransferError, ValidationError) as e:
        error(f'\nError: {e}')
        exit(1)


if __name__ == '__main__':
    cli(prog_name='stackmanager')
