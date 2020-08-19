# stackmanager

[![PyPI version](https://badge.fury.io/py/stackmanager.svg)](https://badge.fury.io/py/stackmanager)
[![Coverage Status](https://coveralls.io/repos/github/LeadingEDJE/stackmanager/badge.svg?branch=master)](https://coveralls.io/github/LeadingEDJE/stackmanager?branch=master)

Utility to manage CloudFormation stacks based upon a Template (either local or in S3) and a YAML configuration file.

Uses ChangeSets to create or update CloudFormation stacks, allowing the ChangeSets to either be automatically
applied or applied later (e.g. during a later phase of a build pipeline after review of the ChangeSet).

> There are also some utility methods for building a lambda file zip and uploading files to S3.
> These are to provide some of the AWS SAM CLI functionality while fitting into the workflow and configuration
> style of stackmanager.

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

## Usage

Stackmanager has the following commands:

* `deploy` - Create or update a CloudFormation stack for a specific environment/region using a ChangeSet. By default exits after creating the changeset, but can `--auto-apply`.
* `apply` - Apply a previously created ChangeSet
* `reject` - Reject a previously created ChangeSet
* `delete` - Delete an existing CloudFormation stack
* `status` - Print current status of Stack
* `upload` - Uploads a local file to S3. Utility method to prevent the need to use the AWS CLI or other tools.
* `build-lambda` - Build a Lambda zip file using aws-lambda-builders.

### deploy

```
Usage: stackmanager deploy [OPTIONS]

  Create or update a CloudFormation stack using ChangeSets.

Options:
  -p, --profile TEXT              AWS Profile, will use default or environment variables if not specified
  -c, --config TEXT               YAML Configuration file  [required]
  -e, --environment TEXT          Environment to deploy  [required]
  -r, --region TEXT               AWS Region to deploy  [required]
  -t, --template TEXT             Override template
  --parameter TEXT...             Override a parameter, can be specified multiple times
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

_(since 0.7.0)_ Existing ChangeSets, if any, will be listed for the stack and depending upon the `--existing-changes`
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
  -c, --config TEXT       YAML Configuration file
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
  -c, --config TEXT       YAML Configuration file
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
  -c, --config TEXT        YAML Configuration file  [required]
  -e, --environment TEXT   Environment to deploy  [required]
  -r, --region TEXT        AWS Region to deploy  [required]
  --retain-resources TEXT  Logical Ids of resources to retain
  --help                   Show this message and exit.
```

### status

```
Usage: stackmanager status [OPTIONS]

  Print current status of Stack. Includes pending ChangeSets and recent events.

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment variables if not specified
  -c, --config TEXT       YAML Configuration file  [required]
  -e, --environment TEXT  Environment to deploy  [required]
  -r, --region TEXT       AWS Region to deploy  [required]
  --event-days INTEGER    Number of days of events to include in output
  --help                  Show this message and exit.
```

### upload

```
Usage: stackmanager upload [OPTIONS]

  Uploads a File to S3. This might be a large CloudFormation template, or a
  Lambda zip file

Options:
  -p, --profile TEXT   AWS Profile, will use default or environment variables if not specified
  -r, --region TEXT    AWS Region to upload to  [required]
  -f, --filename TEXT  File to upload  [required]
  -b, --bucket TEXT    Bucket to upload to  [required]
  -k, --key TEXT       Key to upload to  [required]
  --help               Show this message and exit.
```

### build-lambda

```
Usage: stackmanager build-lambda [OPTIONS]

  Build a Lambda function zip file.

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

## Configuration

> Future plans are to have a global configuration or a larger set of environment variables that can configure
> behavior.

By default displayed timestamps (e.g. for CloudFormation events) will be displayed in the detected local timezone
including the timezone offset. If you specify a timezone using the `STACKMANAGER_TIMEZONE` environment variable
then this will be used instead and the timezone offset will be omitted. Olson Timezones (e.g. America/New_York)
are supported.