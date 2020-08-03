from .exceptions import ValidationError
from .config import Config, ENVIRONMENT, REGION, TEMPLATE, PARAMETERS, CHANGE_SET_NAME, CHANGE_SET_ID, EXISTING_CHANGES, AUTO_APPLY
import yaml


def load_config(config_file, environment, region, check_template=True, **kwargs):
    """
    Build hierarchy of configurations by loading multi-document config file.
    There must be a matching config for the environment name and region.
    :param str config_file: Path to config file
    :param str environment: Environment being updated
    :param str region: Region for the Stack
    :param bool check_template: Check Template exists when validating config
    :param dict kwargs: Other arguments to be added to arg config
    :return: Top of Config hierarchy
    :raises validationException: If config file not found, matching environment not found in config or config is invalid
    """
    arg_config = create_arg_config(environment, region, kwargs)

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


def create_arg_config(environment, region, kwargs):
    """
    Create a Configuration from the command line arguments, used as top of hierarchy to
    optionally override template and parameters.
    :param str environment: Environment
    :param str region: Region to deploy
    :param dict kwargs: Other arguments to be added to arg config
    :return: Argument Config
    """
    raw_config = {
        ENVIRONMENT: environment,
        REGION: region
    }
    if TEMPLATE in kwargs:
        raw_config[TEMPLATE] = kwargs[TEMPLATE]
    if PARAMETERS in kwargs:
        raw_config[PARAMETERS] = dict(kwargs[PARAMETERS])
    if CHANGE_SET_NAME in kwargs:
        raw_config[CHANGE_SET_NAME] = kwargs[CHANGE_SET_NAME]
    if CHANGE_SET_ID in kwargs:
        raw_config[CHANGE_SET_ID] = kwargs[CHANGE_SET_ID]
    if EXISTING_CHANGES in kwargs:
        raw_config[EXISTING_CHANGES] = kwargs[EXISTING_CHANGES]
    if AUTO_APPLY in kwargs:
        raw_config[AUTO_APPLY] = kwargs[AUTO_APPLY]

    return Config(raw_config)
