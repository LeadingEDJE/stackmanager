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
VARIABLES = 'Variables'
TERMINATION_PROTECTION = 'TerminationProtection'


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
        self._config = config
        self._parent = None
        self._environment = config.get(ENVIRONMENT)
        self._region = config.get(REGION)

    @property
    def environment(self):
        return self._environment

    @environment.setter
    def environment(self, environment):
        self._environment = environment
        self._config[ENVIRONMENT] = environment

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, region):
        self._region = region
        self._config[REGION] = region

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        self._parent = parent

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

    def __get_value(self, name, required=False):
        """
        Get value, checking parent if not set
        :param str name: Name of value in raw config
        :param bool required: Is the value required
        :return: Value for name
        :raises ValidationError: If a required value is not available
        """
        value = self._config.get(name)
        if value is None and self.parent:
            value = self.parent.__get_value(name)

        if required and value is None:
            raise ValidationError(f'{name} not set')

        return value

    def __get_list(self, name, default=[]):
        """
        Get list of values, checking parent if not set
        :param str name: Name of value in raw config
        :param list default: Default to return if not set
        :return: Value or default
        """
        values = self._config.get(name)
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
        values = self._config.get(name, {})
        if self.parent:
            copy = self.parent.__get_dict(name).copy()
            copy.update(values)

        return copy if copy else values

    def __get_variables(self):
        """
        Get Variables for templating from the Variables section of the config,
        with the current Environment and Region
        :return: Variables for templating
        """
        variables = self.__get_dict(VARIABLES)
        variables.update(Environment=self.environment, Region=self.region)
        return variables

    def __template_all(self, values):
        """
        Process dictionary, evaluating all values using Jinja2 templates using
        the Environment and Region as replacement values
        :param dict values: Dictionary to template
        :return: Updated dictionary
        """
        variables = self.__get_variables()
        for k, v in values.items():
            template = Template(str(v), optimized=False)
            values[k] = template.render(variables)
        return values

    @property
    def stack_name(self):
        """
        Get Stack Name required property
        :return: Stack name, evaluated as a Jinja2 template
        """
        template = Template(self.__get_value(STACK_NAME, True))
        return template.render(self.__get_variables())

    @property
    def template(self):
        """
        Get Template required property
        :return: Template path or URL
        """
        return self.__get_value(TEMPLATE, True)

    @template.setter
    def template(self, template):
        """
        Set Template
        :param str template: Template path or URL
        """
        self._config[TEMPLATE] = template

    @property
    def parameters(self):
        """
        Get Parameters dictionary, merging values from parent Configs
        and substituting any templated values
        :return: Parameters dictionary
        """
        return self.__template_all(self.__get_dict(PARAMETERS))

    def add_parameters(self, parameters):
        """
        Add dynamic parameters to the underlying configuration
        :param parameters: Parameters to add, can be a dictionary or tuples
        """
        if PARAMETERS in self._config:
            self._config[PARAMETERS].update(dict(parameters))
        else:
            self._config[PARAMETERS] = dict(parameters)

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

    @change_set_name.setter
    def change_set_name(self, change_set_name):
        self._config[CHANGE_SET_NAME] = change_set_name

    @property
    def change_set_id(self):
        return self.__get_value(CHANGE_SET_ID, False)

    @change_set_id.setter
    def change_set_id(self, change_set_id):
        self._config[CHANGE_SET_ID] = change_set_id

    @property
    def existing_changes(self):
        return self.__get_value(EXISTING_CHANGES, False) or 'ALLOW'

    @existing_changes.setter
    def existing_changes(self, existing_changes):
        self._config[EXISTING_CHANGES] = existing_changes

    @property
    def auto_apply(self):
        return self.__get_value(AUTO_APPLY, False) or False

    @auto_apply.setter
    def auto_apply(self, auto_apply):
        self._config[AUTO_APPLY] = auto_apply

    @property
    def termination_protection(self):
        """
        Termination Protection for the stack, defaults to True
        :return bool:
        """
        value = self.__get_value(TERMINATION_PROTECTION, False)
        return True if value is None else bool(value)

    def validate(self, check_template=True):
        """
        Validate that required values are available,
        and if the template is not a URL that it exists on the filesystem
        :param bool check_template: If True and template is not URL, check on filesystem
        :raises ValidationError: If Config is not valid
        """
        if not self.environment:
            raise ValidationError('Environment is required')
        if not Config.is_all(self.environment) and not self.region:
            raise ValidationError('Region is required except for the all config')
        if not self.stack_name:
            raise ValidationError('StackName not set')
        if check_template and not self.template:
            raise ValidationError('Template not set')
        if check_template and not Config.is_template_url(self.template):
            if not os.path.isfile(self.template):
                raise ValidationError(f'Template {self.template} not found')

    def __eq__(self, other):
        """
        Test for Equality
        :param Config other: Other Config object
        """
        return self._config == other._config \
            and self.environment == other.environment \
            and self.region == other.region \
            and self.parent == other.parent
