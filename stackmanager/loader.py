from stackmanager.exceptions import ValidationError
from stackmanager.config import Config
import yaml


def load_config(config_file, environment, region, template, parameters, check_template=True):
    """
    Build hierarchy of configurations by loading multi-document config file.
    There must be a matching config for the environment name and region.
    :param str config_file: Path to config file
    :param str environment: Environment being updated
    :param str region: Region for the Stack
    :param str template: Override value for Template from command line
    :param list parameters: Override values for Parameters from the command line
    :param bool check_template: Check Template exists when validating config
    :return: Top of Config hierarchy
    :raises validationException: If config file not found, matching environment not found in config or config is invalid
    """
    arg_config = create_arg_config(environment, region, template, parameters)

    try:
        with open(config_file) as c:
            raw_configs = yaml.safe_load_all(c)
            all_config = None
            env_config = None
            for rc in raw_configs:
                config = Config(rc)
                if Config.is_all(config.environment):
                    all_config = config
                elif config.environment == environment and config.region == region:
                    env_config = config

            if not env_config:
                raise ValidationError(f'Environment {environment} for {region} not found in {config_file}')

            env_config.set_parent(all_config)
            arg_config.set_parent(env_config)

            # Validate before returning
            arg_config.validate(check_template)
            return arg_config
    except FileNotFoundError:
        raise ValidationError(f'Config file {config_file} not found')


def create_arg_config(environment, region, template, parameters):
    """
    Create a Configuration from the command line arguments, used as top of hierarchy to
    optionally override template and parameters.
    :param str environment: Environment
    :param str region: Region to deploy
    :param str template: Override value for Template from command line
    :param list parameters: Override values for Parameters from the command line
    :return: Argument Config
    """
    raw_config = {
        'Environment': environment,
        'Region': region
    }
    if template:
        raw_config['Template'] = template
    if parameters:
        raw_config['Parameters'] = dict(parameters)
    return Config(raw_config)
