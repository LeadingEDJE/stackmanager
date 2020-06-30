class ValidationError(Exception):
    """Exception thrown when configuration fails validation"""
    pass


class StackError(Exception):
    """Exception thrown when there is an AWS Error managing a CloudFormation stack"""
    pass
