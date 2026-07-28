"""core/minio_file.py — MinIO Skill 文件管理"""
from functools import lru_cache

import boto3
from loguru import logger
from shared.configs.settings import MINIO_BUCKET, MINIO_PASSWORD, MINIO_URL, MINIO_USER

@lru_cache(maxsize=1)
def _s3():
    return boto3.client("s3", endpoint_url=MINIO_URL, aws_access_key_id=MINIO_USER, aws_secret_access_key=MINIO_PASSWORD)


@lru_cache(maxsize=50)
def load_skill(skill_name: str) -> str:
    try:
        obj = _s3().get_object(Bucket=MINIO_BUCKET, Key=f"{skill_name}.md")
        return obj["Body"].read().decode("utf-8")
    except Exception as e:
        logger.warning("Skill '{}' not found: {}", skill_name, e)
        return f"Skill '{skill_name}' 不存在"


def list_skills() -> list[str]:
    resp = _s3().list_objects_v2(Bucket=MINIO_BUCKET)
    return [o["Key"].replace(".md", "") for o in resp.get("Contents", [])]
