import asyncio
import csv
import io
import time
from typing import Optional
from loguru import logger

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.schemas.report import ReportData


class S3Service:
    """Сервис для работы с AWS S3"""

    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.reports_prefix = settings.S3_REPORTS_PREFIX
        self.region = settings.AWS_REGION

    async def _get_s3_client(self):
        """Получение асинхронного S3 клиента"""
        session = aioboto3.Session()

        client_kwargs = {
            "service_name": "s3",
            "region_name": self.region,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        }

        # Добавляем кастомный endpoint если указан
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            logger.info(f"Using custom S3 endpoint: {settings.S3_ENDPOINT_URL}")

        return session.client(**client_kwargs)

    async def upload_report_excel(
        self, report_data: ReportData, file_prefix: str = "yandex_report"
    ) -> Optional[str]:
        """Загрузка отчета в S3 в формате Excel"""
        try:
            from app.converters.excel import (
                csv_to_excel_buffer,
                generate_excel_filename,
                validate_excel_data,
            )

            # Валидируем данные
            if not validate_excel_data(report_data):
                raise ValueError("Invalid report data for Excel conversion")

            # Генерируем имя файла
            file_name = generate_excel_filename(file_prefix)
            s3_key = f"{self.reports_prefix}{file_name}"

            # Конвертируем в Excel
            excel_buffer = csv_to_excel_buffer(report_data)

            # Загружаем в S3
            async with await self._get_s3_client() as s3_client:
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=excel_buffer.getvalue(),
                    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ContentDisposition=f'attachment; filename="{file_name}"',
                )

            logger.info(
                f"✅ Excel report uploaded to S3: s3://{self.bucket_name}/{s3_key}"
            )
            return file_name

        except ClientError as e:
            logger.error(f"❌ AWS S3 error uploading Excel report: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error uploading Excel report to S3: {str(e)}")
            return None

    async def get_report_download_url(
        self, file_name: str, expiration: int = 3600
    ) -> Optional[str]:
        """Получение подписанной ссылки для скачивания отчета"""
        try:
            s3_key = f"{self.reports_prefix}{file_name}"

            async with await self._get_s3_client() as s3_client:
                # Проверяем существование файла
                try:
                    await s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        logger.warning(f"File not found in S3: {s3_key}")
                        return None
                    raise

                # Генерируем подписанную ссылку
                response = await s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expiration,
                )

            logger.info(f"✅ Generated download URL for: {file_name}")
            return response

        except ClientError as e:
            logger.error(f"❌ AWS S3 error generating download URL: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error generating download URL: {str(e)}")
            return None

    async def get_report_preview_url(
        self, file_name: str, expiration: int = 86400  # 24 часа по умолчанию
    ) -> Optional[str]:
        """Получение подписанной ссылки для превью отчета (более долгая ссылка)"""
        try:
            s3_key = f"{self.reports_prefix}{file_name}"

            async with await self._get_s3_client() as s3_client:
                # Проверяем существование файла
                try:
                    await s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        logger.warning(f"File not found in S3: {s3_key}")
                        return None
                    raise

                # Генерируем подписанную ссылку для превью
                response = await s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expiration,
                )

            logger.info(
                f"✅ Generated preview URL for: {file_name} (expires in {expiration}s)"
            )
            return response

        except ClientError as e:
            logger.error(f"❌ AWS S3 error generating preview URL: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error generating preview URL: {str(e)}")
            return None

    async def download_report_content(self, file_name: str) -> Optional[bytes]:
        """Скачивание содержимого Excel файла из S3"""
        try:
            s3_key = f"{self.reports_prefix}{file_name}"

            async with await self._get_s3_client() as s3_client:
                # Проверяем существование файла
                try:
                    await s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        logger.warning(f"File not found in S3: {s3_key}")
                        return None
                    raise

                # Скачиваем файл
                response = await s3_client.get_object(
                    Bucket=self.bucket_name, Key=s3_key
                )
                content = await response["Body"].read()

            logger.info(
                f"✅ Downloaded file from S3: {file_name} ({len(content)} bytes)"
            )
            return content

        except ClientError as e:
            logger.error(f"❌ AWS S3 error downloading file: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error downloading file from S3: {str(e)}")
            return None

    async def delete_report(self, file_name: str) -> bool:
        """Удаление отчета из S3"""
        try:
            s3_key = f"{self.reports_prefix}{file_name}"

            async with await self._get_s3_client() as s3_client:
                await s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)

            logger.info(f"✅ Report deleted from S3: {file_name}")
            return True

        except ClientError as e:
            logger.error(f"❌ AWS S3 error deleting report: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Error deleting report from S3: {str(e)}")
            return False

    async def check_bucket_exists(self) -> bool:
        """Проверка существования S3 бакета"""
        try:
            async with await self._get_s3_client() as s3_client:
                await s3_client.head_bucket(Bucket=self.bucket_name)

            logger.info(f"✅ S3 bucket exists: {self.bucket_name}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                logger.error(f"❌ S3 bucket not found: {self.bucket_name}")
            elif error_code == "403":
                logger.error(f"❌ Access denied to S3 bucket: {self.bucket_name}")
            else:
                logger.error(f"❌ S3 bucket check error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking S3 bucket: {str(e)}")
            return False

    async def list_reports(self, limit: int = 100) -> list:
        """Получение списка отчетов из S3"""
        try:
            async with await self._get_s3_client() as s3_client:
                response = await s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=self.reports_prefix,
                    MaxKeys=limit,
                )

            objects = response.get("Contents", [])
            reports = []

            for obj in objects:
                file_name = obj["Key"].replace(self.reports_prefix, "")
                if file_name:  # Пропускаем директории
                    reports.append(
                        {
                            "file_name": file_name,
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"],
                            "s3_key": obj["Key"],
                        }
                    )

            logger.info(f"✅ Found {len(reports)} reports in S3")
            return reports

        except ClientError as e:
            logger.error(f"❌ AWS S3 error listing reports: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"❌ Error listing reports from S3: {str(e)}")
            return []


# Создаем единственный экземпляр сервиса
s3_service = S3Service()
