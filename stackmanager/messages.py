import click
import tabulate


TABLE_FORMAT = 'simple'


def echo(message):
    """
    Print message without coloring
    :param str message: Message
    """
    click.echo(message)


def info(message):
    """
    Print info level message in green
    :param str message: Message
    """
    click.secho(message, fg='green')


def warn(message):
    """
    Print warning level message in yellow
    :param str message: Message
    """
    click.secho(message, fg='yellow')


def error(message):
    """
    Print error level message in bold red
    :param str message: Message
    """
    click.secho(message, fg='red', bold=True, err=True)


def table(data, headers):
    click.echo(tabulate.tabulate(data, headers=headers, tablefmt=TABLE_FORMAT))
