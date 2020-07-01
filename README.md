# Stack-Manager

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


