# stackmanager

[![PyPI version](https://badge.fury.io/py/stackmanager.svg)](https://badge.fury.io/py/stackmanager)
[![Coverage Status](https://coveralls.io/repos/github/LeadingEDJE/stackmanager/badge.svg?branch=master)](https://coveralls.io/github/LeadingEDJE/stackmanager?branch=master)
[![Docker Images](https://img.shields.io/static/v1?label=docker&message=Amazon%20ECR%20Public%20Gallery&color=blue&logo=docker&style=flat)](https://gallery.ecr.aws/leadingedje/stackmanager)

Utility to manage CloudFormation stacks based upon a Template (either local or in S3) and a YAML configuration file.

Uses ChangeSets to create or update CloudFormation stacks, allowing the ChangeSets to either be automatically
applied or applied later (e.g. during a later phase of a build pipeline after review of the ChangeSet).

> There are also some utility methods for building a lambda file zip and uploading files to S3.
> These are to provide some of the AWS SAM CLI functionality while fitting into the workflow and configuration
> style of stackmanager.

## Installation

stackmanager is available as a [Python package](https://pypi.org/project/stackmanager) or a [Docker image](https://gallery.ecr.aws/leadingedje/stackmanager) based upon Debian.

The Docker image can be used to run container jobs in Azure DevOps pipelines and potentially other CI/CD products.

## Configuration

The configuration file can either be a single YAML document containing the configuration for a stack
for a specific environment and region, or can contain multiple documents for different deployments
of that stack to different environments and regions.

### Single Environment

The configuration combines together the different values that are typically passed to the CloudFormation
command line when creating or updating a CloudFormation stack. 

```yaml
Environment: dev
StackName: "{{ EnvironmentCode }}-StackManager-Integration"
Region: us-east-1
Parameters:
  Environment: "{{ Environment }}"
Tags:
  Application: StackManager
  Environment: "{{ Environment }}"
Variables:
  EnvironmentCode: d
Template: integration/template.yaml
Capabilities:
  - CAPABILITY_NAMED_IAM
```

The configuration file makes use of [Jinja2](https://palletsprojects.com/p/jinja/) templating to perform
replacements into the `StackName`, `Parameters` and `Tags` values using the `Environment` and `Region` values
and any values from the `Variables` section.

> It's also possible to make use of Jinja2 filters, for example to lowercase the Environment to pass into a
> parameter that is going to be used where it's required to be lowercase (e.g. in forming a bucket name):
> 
> ```yaml
> Parameters:
>   LowerEnvironment: "{{ Environment|lower() }}" 
> ```

### Multiple Environments

```yaml
---
Environment: all
StackName: "{{ EnvironmentCode }}-StackManager-Integration-{{ Region }}"
Parameters:
  Environment: "{{ Environment }}"
Tags:
  Application: StackManager
  Environment: "{{ Environment }}"
Template: integration/template.yaml
---
Environment: dev
Region: us-east-1
Variables:
  EnvironmentCode: d
---
Environment: dev
Region: us-east-2
Variables:
  EnvironmentCode: d
---
Environment: prod
Region: us-east-1
Tags:
  CostCenter: 200
Variables:
  EnvironmentCode: p
---
Environment: prod
Region: us-east-2
Tags:
  CostCenter: 300
Variables:
  EnvironmentCode: p
```

A multi-environment configuration can be used to combine all the configurations for different versions of a stack
across environments and regions, using inheritance from a specially named `all` Environment to avoid the need
to repeat values.

> Because of the special handling of the `all` Environment, it's not possible to deploy an environment named `all`.

### Supported Configuration Values

|Name|Required|Templated|Notes|
|:---|:------:|:-------:|:----|
|Environment|Yes|No|Name of environment to be deployed|
|Region|Yes|No|AWS region (e.g. us-east-1) - not required for the 'all' environment|
|Parameters|No|Yes|Each parameter value is templated, and parameters are inherited from 'all'|
|Tags|No|Yes|Each tag value is templated, and tags are inherited from 'all'|
|Variables|No|No|Values are inherited from all and then substituted into StackName, Parameters and Tags|
|Capabilities|No|No|List of capabilities (e.g. CAPABILITY_IAM)
|Template|No|No|Can be supplied on command line, so not required in configuration
|TerminationProtection|No|No|Termination Protection defaults to True|

> In `1.2.0`, Termination Protection support was added and defaults to True, set to False in config.yml to disable.
> When deleting a stack using stackmanager, termination protection will be automatically disabled.

## Usage

Stackmanager has the following commands:

* [`deploy`](#deploy) - Create or update a CloudFormation stack for a specific environment/region using a ChangeSet. By default exits after creating the changeset, but can `--auto-apply`.
* [`apply`](#apply) - Apply a previously created ChangeSet
* [`reject`](#reject) - Reject a previously created ChangeSet
* [`delete`](#delete) - Delete an existing CloudFormation stack
* [`status`](#status) - Print current status of Stack
* [`get-output`](#get-output) - Get Stack Output value
* [`upload`](#upload) - Uploads a local file to S3. Utility method to prevent the need to use the AWS CLI or other tools.
* [`build-lambda`](#build-lambda) - Build a Lambda zip file using aws-lambda-builders.

```
Usage: stackmanager [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

  Utility for managing CloudFormation stacks.

Options:
  -p, --profile TEXT  AWS Profile, will use default or environment variables if not specified
  -r, --region TEXT   AWS Region to deploy
  --help              Show this message and exit.

Commands:
  apply         Apply a CloudFormation ChangeSet to create or update a CloudFormation stack.
  build-lambda  Build a Lambda function zip file.
  delete        Delete a CloudFormation stack.
  deploy        Create or update a CloudFormation stack using ChangeSets.
  get-output    Returns matching Output value if it exists.
  reject        Reject a CloudFormation ChangeSet, deleting the stack if in REVIEW_IN_PROGRESS status and has no other ChangeSets.
  status        Print current status of Stack.
  upload        Uploads a File to S3.

```

The `--profile` and `--region` options can be set either on the root `stackmanager` command, or on the nested commands.

Multiple commands can be chained together, and the sequence of `build-lambda` -> `upload` -> `deploy` can be used to
deploy Lambda functions.

> The path to the Zip file generated by `build-lambda` is passed as the `--filename` option on `upload`, and
> the S3 bucket and key from the `upload` command is passed as parameters to the `deploy` command.

### deploy

```
Usage: stackmanager deploy [OPTIONS]

  Create or update a CloudFormation stack using ChangeSets.

Options:
  -p, --profile TEXT              AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT          YAML Configuration file  [required]
  -e, --environment TEXT          Environment to deploy  [required]
  -r, --region TEXT               AWS Region to deploy  [required]
  -t, --template TEXT             Override template
  --parameter TEXT...             Override a parameter, can be specified multiple times
  --parameter-use-previous TEXT   Use previous value for a parameter, can be specified multiple times
  --change-set-name TEXT          Custom ChangeSet name
  --existing-changes [ALLOW|FAILED_ONLY|DISALLOW]
                                  Whether deployment is allowed when there are
                                  existing ChangeSets
  --auto-apply                    Automatically apply created ChangeSet
  --help                          Show this message and exit.
```

The `--parameter` argument can be supplied multiple times and requires two values (the key and the value),
for example:

```
stackmanager deploy --parameter LambdaBucket mybucket --parameter LambdaKey mykey ...
```

The `--parameter-use-previous` argument can be supplied multiple times and requires one value (the name of the parameter),
and is typically used when a previous run has supplied a `--parameter` argument either as an override or for a value
not included in the configuration.

> If `--parameter` and `--parameter-use-previous` are specified for the same parameter name, the `--parameter`
> value will be used. 

Existing ChangeSets, if any, will be listed for the stack and depending upon the `--existing-changes`
value (which defaults to `ALLOW`) this may prevent the deployment. If set to `FAILED_ONLY` then failed ChangeSets
will not prevent a new change from being created, but if set to `DISALLOW` any existing ChangeSets will prevent new
changes.

### apply

```
Usage: stackmanager apply [OPTIONS]

  Apply a CloudFormation ChangeSet to create or update a CloudFormation stack. 
  If using --change-set-name then --config --environment are --region are required. 
  If using --change-set-id no other values are required (although --profile and --region may be needed).

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT  YAML Configuration file
  -e, --environment TEXT  Environment to deploy
  -r, --region TEXT       AWS Region to deploy
  --change-set-name TEXT  Name of ChangeSet to apply
  --change-set-id TEXT    Identifier of ChangeSet to apply
  --help                  Show this message and exit.
```

_(since 0.7.0)_ Using `--change-set-id` allows you to apply a ChangeSet without loading the configuration.
This can be useful in a CI/CD pipeline as this may avoid the need to checkout the repository for applying a change.

### reject

```
Usage: stackmanager reject [OPTIONS]

  Reject a CloudFormation ChangeSet, deleting the stack if in REVIEW_IN_PROGRESS status and has no other ChangeSets. 
  If using --change-set-name then --config --environment are --region are required. 
  If using --change-set-id no other values are required (although --profile and --region may be needed).

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT  YAML Configuration file
  -e, --environment TEXT  Environment for stack
  -r, --region TEXT       AWS Region for stack
  --change-set-name TEXT  Name of ChangeSet to reject
  --change-set-id TEXT    Identifier of ChangeSet to reject
  --help                  Show this message and exit.
```

### delete

```
Usage: stackmanager delete [OPTIONS]

  Delete a CloudFormation stack.

Options:
  -p, --profile TEXT       AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT   YAML Configuration file  [required]
  -e, --environment TEXT   Environment to deploy  [required]
  -r, --region TEXT        AWS Region to deploy  [required]
  --retain-resources TEXT  Logical Ids of resources to retain
  -Y, --yes                Confirm the action without prompting.
  --help                   Show this message and exit.
```

> Since `1.2.0` deletion requires a confirmation, either interactively or by supplying the `-Y`/`--yes` option.
> Deletion also now automatically removes termination protection (the logic being that you've confirmed you want to delete).

### get-output

Sometimes it's necessary to get an output value from a stack to pass to something else.
While SSM parameter store or CloudFormation exports are a preferred way to pass values between stacks, this can be used
to pass a value from one stackmanager execution to another (e.g. when they are in different regions):

```
myoutput=$(stackmanger get-output -e dev -r us-east-1 -c mystack.yml -o OutputKey)
```

The output value will be the only value written to stdout.

If the stack does not exist, or a matching output does not exist an error will be printed to stderr and the return
code will be -1.

```
Usage: stackmanager get-output [OPTIONS]

  Returns matching Output value if it exists.

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT  YAML Configuration file  [required]
  -e, --environment TEXT  Environment to deploy  [required]
  -r, --region TEXT       AWS Region to deploy
  -o, --output-key TEXT   Output Key  [required]
  --help                  Show this message and exit.
```

### status

```
Usage: stackmanager status [OPTIONS]

  Print current status of Stack. Includes pending ChangeSets and recent events.

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment variables if not specified
  -c, --config-file TEXT  YAML Configuration file  [required]
  -e, --environment TEXT  Environment to deploy  [required]
  -r, --region TEXT       AWS Region to deploy  [required]
  --event-days INTEGER    Number of days of events to include in output
  --help                  Show this message and exit.
```

### upload

```
Usage: stackmanager upload [OPTIONS]

  Uploads a File to S3. This might be a large CloudFormation template, or a
  Lambda zip file. Can be chained into the deploy command where it pre-populates 
  parameters for the uploaded file.

Options:
  -p, --profile TEXT       AWS Profile, will use default or environment variables if not specified
  -r, --region TEXT        AWS Region to upload to
  -f, --filename TEXT      File to upload
  -b, --bucket TEXT        Bucket to upload to  [required]
  -k, --key TEXT           Key to upload to  [required]
  --bucket-parameter TEXT  CloudFormation parameter for Bucket
  --key-parameter TEXT     CloudFormation parameter for Key
  --help                   Show this message and exit.
```

### build-lambda

```
Usage: stackmanager build-lambda [OPTIONS]

  Build a Lambda function zip file. Can be chained into the upload command
  where it pre-populates the --filename option.

Options:
  -s, --source-dir TEXT  Source directory  [required]
  -o, --output-dir TEXT  Output directory  [required]
  --runtime TEXT         Lambda Runtime  [required]
  --archive-name TEXT    Override archive name (defaults to source directory name)
  --help                 Show this message and exit.
```

## CI/CD Pipeline support

### Azure DevOps

Stackmanager will automatically detect when it is running in an Azure DevOps pipeline by looking for the 
`SYSTEM_TEAMPROJECTID` environment variable.

It will print `##vso` strings under the following circumstances:

* `deploy` has created a ChangeSet and it has not been auto-applied: \
  Sets two variables for the ChangeSet name and identifier. These default to `change_set_name` and `change_set_id`
  _(since 0.7.0)_ but the name of these variables can be changed with the `CHANGE_SET_NAME_VARIABLE` and 
  `CHANGE_SET_ID_VARIABLE` environment variables. These values can be used with the `apply` command in a later stage.
* `deploy` has created a ChangeSet but it contains no changes:\
   This logs a warning (`##vso[task.logissue]`) and sets the status to `SucceededWithIssues` (`##vso[task.complete]`)
   allowing following steps/jobs/stages to be skipped by checking for the `SucceededStatus` in a condition.
* `deploy` or `apply` fails when applying a ChangeSet: \
   This logs an error (`##vso[task.logissue]`)

## Additional Configuration

> Future plans are to have a global configuration or a larger set of environment variables that can configure
> behavior.

By default displayed timestamps (e.g. for CloudFormation events) will be displayed in the detected local timezone
including the timezone offset. If you specify a timezone using the `STACKMANAGER_TIMEZONE` environment variable
then this will be used instead and the timezone offset will be omitted. Olson Timezones (e.g. America/New_York)
are supported.