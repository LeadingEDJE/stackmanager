# Stack-Manager

[![PyPI version](https://badge.fury.io/py/stackmanager.svg)](https://badge.fury.io/py/stackmanager)

Utility to manage CloudFormation stacks based upon a Template (either local or in S3) and a YAML configuration file.

Uses ChangeSets to create or update CloudFormation stacks, allowing the ChangeSets to either be automatically
applied or applied later (e.g. during a later phase of a build pipeline after review of the ChangeSet).

## Configuration

The configuration file can either be a single YAML document containing the configuration for a stack
for a specific environment and region, or can contain multiple documents for different deployments
of that stack to different environments and regions.

### Single Environment

The configuration combines together the different values that are typically passed to the CloudFormation
command line when creating or updating a CloudFormation stack. 

```yaml
Environment: dev
StackName: "{{ Environment }}-StackManager-Integration"
Region: us-east-1
Parameters:
  Environment: "{{ Environment }}"
Tags:
  Application: StackManager
  Environment: "{{ Environment }}"
Template: integration/template.yaml
Capabilities:
  - CAPABILITY_NAMED_IAM
```

The configuration file makes use of [Jinja2](https://palletsprojects.com/p/jinja/) templating to perform
replacements into the `StackName`, `Parameters` and `Tags` values using the `Environment` and `Region` values.

> It's also possible to make use of Jinja2 filters, for example to lowercase the Environment to pass into a
> parameter that is going to be used where it's required to be lowercase (e.g. in forming a bucket name):
> 
> ```yaml
> Parameters:
>   LowerEnvironment: "{{ Environment|lower() }}" 
> ```

_There is not currently support for defining and substituting arbitrary values._

### Multiple Environments

```yaml
---
Environment: all
StackName: "{{ Environment }}-StackManager-Integration-{{ Region }}"
Parameters:
  Environment: "{{ Environment }}"
Tags:
  Application: StackManager
  Environment: "{{ Environment }}"
Template: integration/template.yaml
---
Environment: dev
Region: us-east-1
---
Environment: dev
Region: us-east-2
---
Environment: prod
Region: us-east-1
Tags:
  CostCenter: 200
---
Environment: prod
Region: us-east-2
Tags:
  CostCenter: 300
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
|Capabilities|No|No|List of capabilities (e.g. CAPABILITY_IAM)
|Template|No|No|Can be supplied on command line, so not required in configuration

## Usage

Stackmanager has the following commands:

* `deploy` - Create or update a CloudFormation stack for a specific environment/region using a ChangeSet. By default exits after creating the changeset, but can `--auto-apply`.
* `apply` - Apply a previously created ChangeSet
* `delete` - Delete an existing CloudFormation stack

### deploy

```
Usage: stackmanager deploy [OPTIONS]

  Create or update a CloudFormation stack using ChangeSets.

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment
                          variables if not specified

  -c, --config TEXT       YAML Configuration file  [required]
  -e, --environment TEXT  Environment to deploy  [required]
  -r, --region TEXT       AWS Region to deploy  [required]
  -t, --template TEXT     Override template
  --parameter TEXT...     Override a parameter, can be specified multiple
                          times

  --change-set-name TEXT  Custom ChangeSet name
  --auto-apply            Automatically apply created ChangeSet
  --help                  Show this message and exit.
```

### apply

```
Usage: stackmanager apply [OPTIONS]

  Apply a CloudFormation ChangeSet to create or update a CloudFormation
  stack.

Options:
  -p, --profile TEXT      AWS Profile, will use default or environment
                          variables if not specified

  -c, --config TEXT       YAML Configuration file  [required]
  -e, --environment TEXT  Environment to deploy  [required]
  -r, --region TEXT       AWS Region to deploy  [required]
  --change-set-name TEXT  ChangeSet to apply  [required]
  --help                  Show this message and exit.
```

### delete

```
Usage: stackmanager delete [OPTIONS]

  Delete a CloudFormation stack.

Options:
  -p, --profile TEXT       AWS Profile, will use default or environment
                           variables if not specified

  -c, --config TEXT        YAML Configuration file  [required]
  -e, --environment TEXT   Environment to deploy  [required]
  -r, --region TEXT        AWS Region to deploy  [required]
  --retain-resources TEXT  Logical Ids of resources to retain
  --help                   Show this message and exit.
```

## CI/CD Pipeline support

### Azure DevOps

Stackmanager will automatically detect when it is running in an Azure DevOps pipeline by looking for the 
`SYSTEM_TEAMPROJECTID` environment variable.

It will print `##vso` strings under the following circumstances:

* `deploy` has created a ChangeSet and it has not been auto-applied: \
  This sets a variable named `change_set_name` containing the `change_set_name` that can be used with the `apply` 
  command in a later step/job/stage.\
  The name of the variable can be overridden by setting the `CHANGE_SET_VARIABLE` environment variable.
* `deploy` has created a ChangeSet but it contains no changes: \
   This logs a warning (`##vso[task.logissue]`) and sets the status to `SucceededWithIssues` (`##vso[task.complete]`)
   allowing following steps/jobs/stages to be skipped by checking for the `SucceededStatus` in a condition.
* `deploy` or `apply` fails when applying a ChangeSet: \
   This logs an error (`##vso[task.logissue]`)
