import os
from stackmanager.exceptions import ValidationError
from jinja2 import Template


ENVIRONMENT = 'Environment'
REGION = 'Region'
STACK_NAME = 'StackName'
PARAMETERS = 'Parameters'
TEMPLATE = 'Template'
TAGS = 'Tags'
CAPABILITIES = 'Capabilities'
CHANGE_SET_NAME = 'ChangeSetName'
CHANGE_SET_ID = 'ChangeSetId'
EXISTING_CHANGES = 'ExistingChanges'
AUTO_APPLY = 'AutoApply'


class Config:
    """
    Encapsulates Configuration for one of the following:
    - base "all" Environment from which other environments can inherit values
    - environment identified by Environment name and Region
    - arguments that override values from command line
    If a parent is defined, values from the parent Config act as a default,
    and are merged for parameters and tags.
    """

    def __init__(self, config):
        """
        Initialize Configuration
        :param dict config: Raw Configuration dictionary
        :raises ValidationError: if Environment or Region is missing when required
        """
        self.parent = None
        self.config = config
        self.environment = config.get(ENVIRONMENT)
        self.region = config.get(REGION)

        if not self.environment:
            raise ValidationError('Environment is required')

        if not Config.is_all(self.environment) and not self.region:
            raise ValidationError('Region is required except for the all config')

    @classmethod
    def is_all(cls, environment):
        """
        Is this environment name the base all environment
        :param str environment: Environment name
        :return: True if name is all
        """
        return environment == 'all'

    @classmethod
    def is_template_url(cls, template):
        """
        Is the template value a URL (starting with https://) or not
        :param str template: Template path or URL
        :return: True if this is a URL
        """
        return template.startswith('https://')

    def set_parent(self, parent):
        """
        Set the parent Config
        :param Config parent: Parent Config
        """
        self.parent = parent

    def __get_value(self, name, required=False):
        """
        Get value, checking parent if not set
        :param str name: Name of value in raw config
        :param bool required: Is the value required
        :return: Value for name
        :raises ValidationError: If a required value is not available
        """
        value = self.config.get(name)
        if not value and self.parent:
            value = self.parent.__get_value(name)

        if required and not value:
            raise ValidationError(f'{name} not set')

        return value

    def __get_list(self, name, default=[]):
        """
        Get list of values, checking parent if not set
        :param str name: Name of value in raw config
        :param list default: Default to return if not set
        :return: Value or default
        """
        values = self.config.get(name)
        if not values and self.parent:
            values = self.parent.__get_list(name, None)

        return values if values else default

    def __get_dict(self, name):
        """
        Get dictionary of values, merging with parent values if available.
        Values from the parent are overwritten if redefined in the child Config
        :param str name: Name of dictionary of values
        :return: Merged values, or empty dictionary
        """
        copy = None
        values = self.config.get(name, {})
        if self.parent:
            copy = self.parent.__get_dict(name).copy()
            copy.update(values)

        return copy if copy else values

    def __template_all(self, values):
        """
        Process dictionary, evaluating all values using Jinja2 templates using
        the Environment and Region as replacement values
        :param dict values: Dictionary to template
        :return: Updated dictionary
        """
        for k, v in values.items():
            template = Template(str(v), optimized=False)
            values[k] = template.render(Environment=self.environment, Region=self.region)
        return values

    @property
    def stack_name(self):
        """
        Get Stack Name required property
        :return: Stack name, evaluated as a Jinja2 template
        """
        template = Template(self.__get_value(STACK_NAME, True))
        return template.render(Environment=self.environment, Region=self.region)

    @property
    def template(self):
        """
        Get Template required property
        :return: Template path or URL
        """
        return self.__get_value(TEMPLATE, True)

    @property
    def parameters(self):
        """
        Get Parameters dictionary, merging values from parent Configs
        and substituting any templated values
        :return: Parameters dictionary
        """
        return self.__template_all(self.__get_dict(PARAMETERS))

    @property
    def tags(self):
        """
        Get Tags dictionary, merging values from parent Configs
        and substituting any templated values
        :return: Tags dictionary
        """
        return self.__template_all(self.__get_dict(TAGS))

    @property
    def capabilities(self):
        """
        Get list of capabilities
        :return: Capabilities
        """
        return self.__get_list(CAPABILITIES)

    @property
    def change_set_name(self):
        return self.__get_value(CHANGE_SET_NAME, False)

    @property
    def change_set_id(self):
        return self.__get_value(CHANGE_SET_ID, False)

    @property
    def existing_changes(self):
        return self.__get_value(EXISTING_CHANGES, True)

    @property
    def auto_apply(self):
        return self.__get_value(AUTO_APPLY, False) or False

    def validate(self, check_template=True):
        """
        Validate that required values are available,
        and if the template is not a URL that it exists on the filesystem
        :param bool check_template: If True and template is not URL, check on filesystem
        :raises ValidationError: If Config is not valid
        """
        if not self.stack_name:
            raise ValidationError('StackName not set')
        if check_template and not self.template:
            raise ValidationError('Template not set')
        if check_template and not Config.is_template_url(self.template):
            if not os.path.isfile(self.template):
                raise ValidationError(f'Template {self.template} not found')
