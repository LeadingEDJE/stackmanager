import tempfile
import os
from stackmanager.exceptions import PackagingError, ValidationError
from stackmanager.messages import info
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError
from collections import namedtuple
from shutil import make_archive

CONFIG = namedtuple('Capability', ['language', 'dependency_manager', 'manifest_name'])

PYTHON_PIP_CONFIG = CONFIG(language='python', dependency_manager='pip', manifest_name='requirements.txt')
NODEJS_NPM_CONFIG = CONFIG(language='nodejs', dependency_manager='npm', manifest_name='package.json')
RUBY_BUNDLER_CONFIG = CONFIG(language='ruby', dependency_manager='bundler', manifest_name='Gemfile')
JAVA_GRADLE_CONFIG = CONFIG(language='java', dependency_manager='gradle', manifest_name='build.gradle')
JAVA_KOTLIN_GRADLE_CONFIG = CONFIG(language='java', dependency_manager='gradle', manifest_name='build.gradle.kts')
JAVA_MAVEN_CONFIG = CONFIG(language='java', dependency_manager='maven', manifest_name='pom.xml')
DOTNET_CLIPACKAGE_CONFIG = CONFIG(language='dotnet', dependency_manager='cli-package', manifest_name='.csproj')
GO_MOD_CONFIG = CONFIG(language='go', dependency_manager='modules', manifest_name='go.mod')

RUNTIMES = {
    'python2.7': PYTHON_PIP_CONFIG,
    'python3.6': PYTHON_PIP_CONFIG,
    'python3.7': PYTHON_PIP_CONFIG,
    'python3.8': PYTHON_PIP_CONFIG,
    'dotnetcore2.1': DOTNET_CLIPACKAGE_CONFIG,
    'dotnetcore3.1': DOTNET_CLIPACKAGE_CONFIG,
    'nodejs10.x': NODEJS_NPM_CONFIG,
    'nodejs12.x': NODEJS_NPM_CONFIG,
    'ruby2.5': RUBY_BUNDLER_CONFIG,
    'ruby2.7': RUBY_BUNDLER_CONFIG,
    'go1.x': GO_MOD_CONFIG,
    'java8': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG],
    'java11': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG]
}


def get_config(runtime, source_dir):
    """
    Get Configuration matching the runtime.
    If there are multiple configurations for the runtime, look for manifest file matching config.
    :param runtime: Lambda Runtime
    :param source_dir: Source Directory
    :return: Configuration
    :raises ValidationError: if matching runtime not found
    """
    if runtime not in RUNTIMES:
        raise ValidationError(f'Unsupported Runtime {runtime}')

    if isinstance(RUNTIMES[runtime], list):
        configs = RUNTIMES[runtime]
        for config in configs:
            if os.path.isfile(os.path.join(source_dir, config.manifest_name)):
                return config
        raise ValidationError(f'Cannot find suitable manifest for Runtime {runtime}')

    return RUNTIMES[runtime]


def build_lambda(source_dir, output_dir, runtime, archive_name):
    """
    Build a Lambda Function zip using a builder from aws-lambda-builders
    :param source_dir: Source Directory
    :param output_dir: Output Directory
    :param runtime: Lambda Runtime
    :param archive_name: Archive name (optional)
    """
    config = get_config(runtime, source_dir)
    builder = LambdaBuilder(config.language, config.dependency_manager, None)
    manifest_path = os.path.join(source_dir, config.manifest_name)
    archive_name = archive_name if archive_name else os.path.basename(os.path.normpath(source_dir))

    with tempfile.TemporaryDirectory() as artifacts_dir:
        with tempfile.TemporaryDirectory() as scratch_dir:
            try:
                builder.build(source_dir, artifacts_dir, scratch_dir, manifest_path, runtime)
                zip_file = make_archive(os.path.join(output_dir, archive_name), 'zip', artifacts_dir)
                info(f'\nBuilt Lambda Archive {zip_file}')
            except LambdaBuilderError as e:
                raise PackagingError(e)
