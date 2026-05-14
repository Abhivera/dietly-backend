import logging
import uuid
from typing import Any, Dict, Optional, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self) -> None:
        self.aws_access_key_id = settings.aws_access_key_id
        self.aws_secret_access_key = settings.aws_secret_access_key
        self.aws_region = settings.aws_region
        self.bucket_name = settings.aws_s3_bucket_name

        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name]):
            missing = [
                n
                for n, v in (
                    ("AWS_ACCESS_KEY_ID", self.aws_access_key_id),
                    ("AWS_SECRET_ACCESS_KEY", self.aws_secret_access_key),
                    ("AWS_S3_BUCKET_NAME", self.bucket_name),
                )
                if not v
            ]
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
            )
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info("S3 client initialized")
        except (ClientError, NoCredentialsError) as e:
            raise ValueError("Could not initialize S3 client; check credentials and bucket access") from e

    def upload_file(self, file_obj, user_id: Union[int, str], original_filename: str) -> Dict[str, Any]:
        try:
            file_extension = original_filename.split(".")[-1].lower()
            unique_filename = f"{user_id}/{uuid.uuid4().hex}.{file_extension}"
            file_obj.seek(0)
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                unique_filename,
                ExtraArgs={
                    "ContentType": self._get_content_type(file_extension),
                    "ServerSideEncryption": "AES256",
                },
            )
            file_url = self.generate_presigned_url(unique_filename, expiration=86400)
            return {
                "success": True,
                "filename": unique_filename,
                "original_filename": original_filename,
                "file_url": file_url,
                "s3_key": unique_filename,
                "bucket": self.bucket_name,
            }
        except ClientError as e:
            logger.error("AWS S3 error: %s", e)
            return {"success": False, "error": f"S3 upload failed: {e}"}
        except Exception as e:
            logger.error("Upload error: %s", e)
            return {"success": False, "error": f"Upload failed: {e}"}

    def delete_file(self, s3_key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error("S3 delete error: %s", e)
            return False

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        try:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logger.error("Error generating presigned URL: %s", e)
            return None

    def get_file_content(self, s3_key: str) -> Optional[bytes]:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error("Error getting file content: %s", e)
            return None

    def upload_file_with_public_access(
        self, file_obj, user_id: Union[int, str], original_filename: str
    ) -> Dict[str, Any]:
        try:
            file_extension = original_filename.split(".")[-1].lower()
            unique_filename = f"{user_id}/{uuid.uuid4().hex}.{file_extension}"
            file_obj.seek(0)
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                unique_filename,
                ExtraArgs={
                    "ContentType": self._get_content_type(file_extension),
                    "ServerSideEncryption": "AES256",
                },
            )
            file_url = f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{unique_filename}"
            return {
                "success": True,
                "filename": unique_filename,
                "original_filename": original_filename,
                "file_url": file_url,
                "s3_key": unique_filename,
                "bucket": self.bucket_name,
            }
        except ClientError as e:
            logger.error("AWS S3 error: %s", e)
            return {"success": False, "error": f"S3 upload failed: {e}"}
        except Exception as e:
            logger.error("Upload error: %s", e)
            return {"success": False, "error": f"Upload failed: {e}"}

    def _get_content_type(self, file_extension: str) -> str:
        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
        }
        return content_types.get(file_extension.lower(), "application/octet-stream")
