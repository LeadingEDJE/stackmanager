import os
from stackmanager.exceptions import ValidationError
from jinja2 import Template


class Config:

    def __init__(self, config):
        self.parent = None
        self.config = config
        self.environment = config.get('Environment')
        self.region = config.get('Region')

        if not self.environment:
            raise ValidationError('Environment is required')

        if not Config.is_all(self.environment) and not self.region:
            raise ValidationError('Region is required except for the all config')

    @classmethod
    def is_all(cls, environment):
        return environment == 'all'

    @classmethod
    def is_template_url(cls, template):
        return template.startswith('https://')

    def set_parent(self, parent):
        self.parent = parent

    def __get_value(self, name, required=False):
        value = self.config.get(name)
        if not value and self.parent:
            value = self.parent.__get_value(name)

        if required and not value:
            raise ValidationError(f'{name} not set')

        return value

    def __get_list(self, name, default=[]):
        values = self.config.get(name)
        if not values and self.parent:
            values = self.parent.__get_list(name, None)

        return values if values else default

    def __get_dict(self, name):
        copy = None
        values = self.config.get(name, {})
        if self.parent:
            copy = self.parent.__get_dict(name).copy()
            copy.update(values)

        return copy if copy else values

    def __template_all(self, values):
        for k, v in values.items():
            template = Template(v, optimized=False)
            values[k] = template.render(Environment=self.environment, Region=self.region)
        return values

    @property
    def stack_name(self):
        template = Template(self.__get_value('StackName', True))
        return template.render(Environment=self.environment, Region=self.region)

    @property
    def template(self):
        return self.__get_value('Template', True)

    @property
    def parameters(self):
        return self.__template_all(self.__get_dict('Parameters'))

    @property
    def tags(self):
        return self.__template_all(self.__get_dict('Tags'))

    @property
    def capabilities(self):
        return self.__get_list('Capabilities')

    def validate(self):
        """Check that we have all the required values for a minimal stack"""
        if not self.stack_name:
            raise ValidationError('StackName not set')
        if not self.template:
            raise ValidationError('Template not set')

        if not Config.is_template_url(self.template):
            if not os.path.isfile(self.template):
                raise ValidationError(f'Template {self.template} not found')
