import click


def info(message):
    click.secho(message, fg='green')


def warn(message):
    click.secho(message, fg='yellow')


def error(message):
    click.secho(message, fg='red', bold=True)