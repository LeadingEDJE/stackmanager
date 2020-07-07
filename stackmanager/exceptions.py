class ValidationError(Exception):
    """Exception thrown when configuration fails validation"""
    pass


class StackError(Exception):
    """Exception thrown when there is an AWS Error managing a CloudFormation stack"""
    pass


class TransferError(Exception):
    """Exception thrown when there is an AWS Error transferring files to S3"""
    pass


class PackagingError(Exception):
    """Exception thrown when unable to package a Lambda Function"""
    pass
