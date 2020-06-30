from stackmanager.exceptions import ValidationError
from stackmanager.config import Config
import yaml


def load_config(config_file, environment, region, template, parameters):
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
            arg_config.validate()
            return arg_config
    except FileNotFoundError:
        raise ValidationError(f'Config file {config_file} not found')


def create_arg_config(environment, region, template, parameters):
    raw_config = {
        'Environment': environment,
        'Region': region
    }
    if template:
        raw_config['Template'] = template
    if parameters:
        raw_config['Parameters'] = dict(parameters)
    return Config(raw_config)
