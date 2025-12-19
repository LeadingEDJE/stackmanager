import logging
import os
import tempfile
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
    'python3.9': PYTHON_PIP_CONFIG,
    'python3.10': PYTHON_PIP_CONFIG,
    'python3.11': PYTHON_PIP_CONFIG,
    'python3.12': PYTHON_PIP_CONFIG,
    'python3.13': PYTHON_PIP_CONFIG,
    'python3.14': PYTHON_PIP_CONFIG,
    'dotnetcore3.1': DOTNET_CLIPACKAGE_CONFIG,
    'dotnet8': DOTNET_CLIPACKAGE_CONFIG,
    'dotnet9': DOTNET_CLIPACKAGE_CONFIG,
    'nodejs20.x': NODEJS_NPM_CONFIG,
    'nodejs22.x': NODEJS_NPM_CONFIG,
    'nodejs24.x': NODEJS_NPM_CONFIG,
    'ruby3.2': RUBY_BUNDLER_CONFIG,
    'ruby3.3': RUBY_BUNDLER_CONFIG,
    'ruby3.4': RUBY_BUNDLER_CONFIG,
    'provided.al2': GO_MOD_CONFIG,
    'provided.al2023': GO_MOD_CONFIG,
    'java8.al2': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG],
    'java11': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG],
    'java17': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG],
    'java21': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG],
    'java25': [JAVA_MAVEN_CONFIG, JAVA_GRADLE_CONFIG, JAVA_KOTLIN_GRADLE_CONFIG]
}

# Configure logging for aws_lambda_builders
log_stream_handler = logging.StreamHandler()
log_stream_handler.setLevel(logging.DEBUG)
log_stream_handler.setFormatter(logging.Formatter("%(message)s"))

build_logger = logging.getLogger("aws_lambda_builders")
build_logger.setLevel(logging.INFO)
build_logger.propagate = False
build_logger.addHandler(log_stream_handler)


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
    :return: Path to generated zip file
    """
    config = get_config(runtime, source_dir)
    builder = LambdaBuilder(config.language, config.dependency_manager, None)
    manifest_path = os.path.join(source_dir, config.manifest_name)
    archive_name = archive_name if archive_name else os.path.basename(os.path.normpath(source_dir))

    info(f'\nBuilding {runtime} Lambda function from {source_dir}\n')

    with tempfile.TemporaryDirectory() as artifacts_dir:
        with tempfile.TemporaryDirectory() as scratch_dir:
            try:
                builder.build(source_dir, artifacts_dir, scratch_dir, manifest_path, runtime)
                zip_file = make_archive(os.path.join(output_dir, archive_name), 'zip', artifacts_dir)
                info(f'\nBuilt Lambda Archive {zip_file}')
                return zip_file
            except LambdaBuilderError as e:
                raise PackagingError(e)
