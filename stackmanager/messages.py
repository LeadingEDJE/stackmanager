import click


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
    click.secho(message, fg='red', bold=True)
