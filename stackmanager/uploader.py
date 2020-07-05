import boto3
from boto3.exceptions import Boto3Error
from botocore.exceptions import ClientError
from stackmanager.exceptions import TransferError, ValidationError
from stackmanager.messages import info


class Uploader:
    """Utility for uploading files to S3"""

    def __init__(self, client):
        self._client = client

    def upload(self, filename, bucket, key, acl='bucket-owner-full-control'):
        """
        Uploads a local file to S3.
        :param filename: Name of local file
        :param bucket: S3 Bucket Name
        :param key: S3 Key
        :param acl: Object ACL, defaults to bucket-owner-full-control
        :raises ValidationError: If local file does not exist
        :raises TransferError: If there is an error uploading the file
        """
        try:
            self._client.upload_file(Filename=filename, Bucket=bucket, Key=key,
                                     ExtraArgs={'ACL': acl})
            info(f'\nUploaded {filename} to s3://{bucket}/{key}')
        except FileNotFoundError:
            raise ValidationError(f'File {filename} not found')
        except (Boto3Error, ClientError) as e:
            raise TransferError(e)


def create_uploader(profile, region):
    """
    Create a new Uploader
    :param profile: AWS Profile
    :param region: AWS Region
    :return: Configured Uploader
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client('s3')
    return Uploader(client)
