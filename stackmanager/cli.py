#!/usr/bin/env python
import click
from stackmanager.exceptions import StackError, ValidationError
from stackmanager.loader import load_config
from stackmanager.messages import error
from stackmanager.runner import create_runner


@click.group(chain=True)
@click.pass_context
def cli(ctx):
    ctx.obj = dict()


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('-t', '--template', help='Override template')
@click.option('--parameter', nargs=2, multiple=True, help='Override a parameter, can be specified multiple times')
@click.option('--change-set-name', help='Custom change set name')
@click.option('--auto-approve', is_flag=True, help='Auto approve change set')
def deploy(ctx, profile, config, environment, region, template, parameter, change_set_name, auto_approve):
    try:
        cfg = load_config(config, environment, region, template, parameter)
        runner = create_runner(profile, cfg, change_set_name, auto_approve)
        runner.deploy()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('--change-set-name', help='Custom change set name')
def apply(ctx, profile, config, environment, region, change_set_name):
    try:
        cfg = load_config(config, environment, region, None, None)
        runner = create_runner(profile, cfg, change_set_name, False)
        runner.execute_change_set()
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')


@cli.command()
@click.pass_context
@click.option('-p', '--profile', help='AWS Profile, will use default or environment variables if not specified')
@click.option('-c', '--config', required=True, help='YAML Configuration file')
@click.option('-e', '--environment', required=True, help='Environment to deploy')
@click.option('-r', '--region', required=True, help='AWS Region to deploy')
@click.option('--retain-resources', multiple=True, help='Logical Ids of resources to retain')
def delete(ctx, profile, config, environment, region, retain_resources):
    try:
        cfg = load_config(config, environment, region, None, None)
        runner = create_runner(profile, cfg, None, False)
        runner.delete(retain_resources)
    except (ValidationError, StackError) as e:
        error(f'\nError: {e}')


if __name__ == '__main__':
    cli()
