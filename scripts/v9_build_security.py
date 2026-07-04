"""Shared build-context and image-scan helpers for v9 cloud safety."""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

V9_IMAGE_MARKER = "tech-cartography-v9-signal-watch"
STUDY_DEMO_IMAGE_MARKER = "tech-cartography-v9-study-demo"
EXCLUDED_BUILD_MARKERS = ("tech-cartography-v7-", "tech-cartography-v8-")

FORBIDDEN_UPLOAD_PATTERNS = (
  ".env",
  ".env.*",
  "config/v9_weekly_run_config.local.json",
  "data/v9_runs",
  "data/v9_runs/**",
  ".streamlit/secrets.toml",
  "credentials",
  "credentials/**",
  "application_default_credentials.json",
  "service-account*.json",
  "*.pem",
  "*.p12",
)
FORBIDDEN_IMAGE_PATTERNS = (
  ".env",
  "**/.env",
  "**/.env.*",
  "app/config/v9_weekly_run_config.local.json",
  "**/config/v9_weekly_run_config.local.json",
  "**/data/v9_runs",
  "**/data/v9_runs/**",
  "**/.streamlit/secrets.toml",
  "**/application_default_credentials.json",
  "**/service-account*.json",
)
IMAGE_PEM_SUFFIXES = (".pem", ".p12")
IMAGE_PEM_EXCLUDE_PREFIXES = (
  "etc/ssl/",
  "usr/lib/ssl/",
  "usr/local/lib/python",
)
IMAGE_PEM_EXCLUDE_SUFFIXES = (
  "/site-packages/certifi/cacert.pem",
  "/site-packages/grpc/_cython/_credentials/roots.pem",
  "/site-packages/pip/_vendor/certifi/cacert.pem",
)
FORBIDDEN_IMAGE_ENV_KEYS = {
  "SMTP_PASSWORD",
  "TAVILY_API_KEY",
  "GOOGLE_API_KEY",
  "OPENAI_API_KEY",
  "GOOGLE_APPLICATION_CREDENTIALS_JSON",
}
REQUIRED_UPLOAD_EXACT = ("Dockerfile.v9", "cloudbuild.v9.yaml", "app.py")
REQUIRED_UPLOAD_PREFIXES = ("services_v9/", "ui_v9/", "scripts/")
SENSITIVE_ENV_NAME_TOKENS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
ARCHIVE_CREDENTIAL_PATTERNS = (
  ".streamlit/secrets.toml",
  "credentials",
  "credentials/**",
  "application_default_credentials.json",
  "service-account*.json",
  "*.pem",
  "*.p12",
)


def normalize_posix_path(path: str) -> str:
  text = str(path or "").replace("\\", "/").strip()
  while text.startswith("./"):
    text = text[2:]
  text = text.lstrip("/")
  if text.endswith("/") and text != "/":
    text = text.rstrip("/")
  return text


def _match_path(path: str, pattern: str) -> bool:
  normalized = normalize_posix_path(path)
  normalized_pattern = normalize_posix_path(pattern)
  if not normalized or not normalized_pattern:
    return False
  if normalized_pattern.endswith("/**"):
    prefix = normalized_pattern[:-3].rstrip("/")
    if prefix.startswith("**/"):
      core = prefix[3:].strip("/")
      return (
        normalized == core
        or normalized.startswith(core + "/")
        or normalized.endswith("/" + core)
        or f"/{core}/" in f"/{normalized}/"
      )
    return normalized == prefix or normalized.startswith(prefix + "/")
  if normalized == normalized_pattern:
    return True
  pure = PurePosixPath(normalized)
  return pure.match(normalized_pattern) or fnmatch.fnmatch(normalized, normalized_pattern)


def is_excluded_image_pem_path(path: str) -> bool:
  normalized = normalize_posix_path(path)
  if not normalized:
    return False
  lowered = normalized.lower()
  if not any(lowered.endswith(suffix) for suffix in IMAGE_PEM_SUFFIXES):
    return False
  if any(lowered.startswith(prefix) for prefix in IMAGE_PEM_EXCLUDE_PREFIXES):
    return True
  return any(lowered.endswith(suffix) for suffix in IMAGE_PEM_EXCLUDE_SUFFIXES)


def is_forbidden_image_pem_path(path: str) -> bool:
  normalized = normalize_posix_path(path)
  if not normalized:
    return False
  lowered = normalized.lower()
  if not any(lowered.endswith(suffix) for suffix in IMAGE_PEM_SUFFIXES):
    return False
  return not is_excluded_image_pem_path(normalized)


def find_matching_paths(paths: Iterable[str], patterns: Iterable[str]) -> list[str]:
  matches: list[str] = []
  seen: set[str] = set()
  for raw_path in paths:
    normalized = normalize_posix_path(raw_path)
    if not normalized:
      continue
    if any(_match_path(normalized, pattern) for pattern in patterns):
      if normalized not in seen:
        seen.add(normalized)
        matches.append(normalized)
  return sorted(matches)


def validate_upload_file_list(paths: Iterable[str], *, minimum_count: int = 20) -> dict[str, Any]:
  normalized = sorted({normalize_posix_path(path) for path in paths if normalize_posix_path(path)})
  forbidden_matches = find_matching_paths(normalized, FORBIDDEN_UPLOAD_PATTERNS)
  missing_required = [
    required
    for required in REQUIRED_UPLOAD_EXACT
    if required not in normalized
  ]
  missing_prefixes = [
    prefix
    for prefix in REQUIRED_UPLOAD_PREFIXES
    if not any(path.startswith(prefix) for path in normalized)
  ]
  too_few_files = len(normalized) < minimum_count
  return {
    "status": "ok" if not forbidden_matches and not missing_required and not missing_prefixes and not too_few_files else "failed",
    "upload_file_count": len(normalized),
    "forbidden_matches": forbidden_matches,
    "forbidden_match_count": len(forbidden_matches),
    "missing_required_files": missing_required,
    "missing_required_prefixes": missing_prefixes,
    "too_few_files": too_few_files,
  }


def summarize_archive_presence(paths: Iterable[str]) -> dict[str, bool]:
  normalized = sorted({normalize_posix_path(path) for path in paths if normalize_posix_path(path)})
  return {
    ".env_present": any(_match_path(path, ".env") for path in normalized),
    ".env_glob_present": any(_match_path(path, ".env.*") for path in normalized),
    "local_config_present": any(_match_path(path, "config/v9_weekly_run_config.local.json") for path in normalized),
    "data_v9_runs_present": any(_match_path(path, "data/v9_runs") or _match_path(path, "data/v9_runs/**") for path in normalized),
    "other_credential_filename_present": bool(find_matching_paths(normalized, ARCHIVE_CREDENTIAL_PATTERNS)),
  }


def extract_env_key_names(env_entries: Iterable[str]) -> list[str]:
  keys: list[str] = []
  seen: set[str] = set()
  for entry in env_entries:
    text = str(entry or "").strip()
    if not text:
      continue
    key = text.split("=", 1)[0].strip()
    if key and key not in seen:
      seen.add(key)
      keys.append(key)
  return sorted(keys)


def scan_image_context(file_paths: Iterable[str], env_entries: Iterable[str]) -> dict[str, Any]:
  normalized_files = sorted({normalize_posix_path(path) for path in file_paths if normalize_posix_path(path)})
  env_keys = extract_env_key_names(env_entries)
  forbidden_file_paths = find_matching_paths(normalized_files, FORBIDDEN_IMAGE_PATTERNS)
  forbidden_file_paths.extend(
    path for path in normalized_files
    if is_forbidden_image_pem_path(path) and path not in forbidden_file_paths
  )
  forbidden_file_paths = sorted(set(forbidden_file_paths))
  forbidden_env_keys = sorted(key for key in env_keys if key in FORBIDDEN_IMAGE_ENV_KEYS)
  return {
    "status": "ok" if not forbidden_file_paths and not forbidden_env_keys else "failed",
    "forbidden_file_paths": forbidden_file_paths,
    "forbidden_file_count": len(forbidden_file_paths),
    "forbidden_env_keys": forbidden_env_keys,
    "forbidden_env_key_count": len(forbidden_env_keys),
  }


def extract_nonempty_sensitive_env_names(dotenv_path: Path) -> list[str]:
  names: list[str] = []
  if not dotenv_path.exists():
    return names
  seen: set[str] = set()
  for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip("\"").strip("'")
    if not key or not value:
      continue
    if any(token in key.upper() for token in SENSITIVE_ENV_NAME_TOKENS) and key not in seen:
      seen.add(key)
      names.append(key)
  return sorted(names)


def _collect_build_strings(build_payload: dict[str, Any]) -> list[str]:
  strings: list[str] = []
  substitutions = dict(build_payload.get("substitutions", {}) or {})
  for value in substitutions.values():
    strings.append(str(value or ""))
  for name in build_payload.get("images", []) or []:
    strings.append(str(name or ""))
  results = dict(build_payload.get("results", {}) or {})
  for image in results.get("images", []) or []:
    if isinstance(image, dict):
      strings.append(str(image.get("name", "") or ""))
      strings.append(str(image.get("digest", "") or ""))
    else:
      strings.append(str(image or ""))
  for step in build_payload.get("steps", []) or []:
    for arg in step.get("args", []) or []:
      strings.append(str(arg or ""))
  return strings


def is_v9_build(build_payload: dict[str, Any]) -> bool:
  strings = _collect_build_strings(build_payload)
  joined = "\n".join(strings)
  if V9_IMAGE_MARKER not in joined and STUDY_DEMO_IMAGE_MARKER not in joined:
    return False
  return not any(marker in joined for marker in EXCLUDED_BUILD_MARKERS)


def extract_source_ref(build_payload: dict[str, Any]) -> dict[str, str]:
  source = dict(build_payload.get("source", {}) or {})
  storage_source = dict(source.get("storageSource", {}) or {})
  return {
    "bucket": str(storage_source.get("bucket", "") or ""),
    "object": str(storage_source.get("object", "") or ""),
    "generation": str(storage_source.get("generation", "") or ""),
  }


def build_source_cleanup_target(build_payload: dict[str, Any]) -> dict[str, Any]:
  if not is_v9_build(build_payload):
    return {"status": "blocked", "reason": "not_v9_build", "bucket": "", "object": "", "generation": ""}
  source_ref = extract_source_ref(build_payload)
  bucket = str(source_ref["bucket"] or "").strip()
  object_name = str(source_ref["object"] or "").strip()
  generation = str(source_ref["generation"] or "").strip()
  if not bucket or not object_name:
    return {"status": "blocked", "reason": "missing_source_ref", "bucket": bucket, "object": object_name, "generation": generation}
  if bucket.endswith(".cloudbuild-logs.googleusercontent.com"):
    return {"status": "blocked", "reason": "log_bucket", "bucket": bucket, "object": object_name, "generation": generation}
  if not object_name.startswith("source/"):
    return {"status": "blocked", "reason": "not_source_object", "bucket": bucket, "object": object_name, "generation": generation}
  return {"status": "ok", "reason": "", "bucket": bucket, "object": object_name, "generation": generation}


def summarize_build_record(build_payload: dict[str, Any]) -> dict[str, Any]:
  source_ref = extract_source_ref(build_payload)
  results = dict(build_payload.get("results", {}) or {})
  result_images: list[dict[str, str]] = []
  for item in results.get("images", []) or []:
    if isinstance(item, dict):
      result_images.append({
        "name": str(item.get("name", "") or ""),
        "digest": str(item.get("digest", "") or ""),
      })
  return {
    "build_id": str(build_payload.get("id", "") or ""),
    "create_time": str(build_payload.get("createTime", "") or ""),
    "status": str(build_payload.get("status", "") or ""),
    "source_bucket": source_ref["bucket"],
    "source_object": source_ref["object"],
    "source_generation": source_ref["generation"],
    "result_images": result_images,
  }


__all__ = [
  "ARCHIVE_CREDENTIAL_PATTERNS",
  "EXCLUDED_BUILD_MARKERS",
  "FORBIDDEN_IMAGE_ENV_KEYS",
  "FORBIDDEN_IMAGE_PATTERNS",
  "FORBIDDEN_UPLOAD_PATTERNS",
  "IMAGE_PEM_EXCLUDE_PREFIXES",
  "IMAGE_PEM_EXCLUDE_SUFFIXES",
  "IMAGE_PEM_SUFFIXES",
  "is_excluded_image_pem_path",
  "is_forbidden_image_pem_path",
  "REQUIRED_UPLOAD_EXACT",
  "REQUIRED_UPLOAD_PREFIXES",
  "V9_IMAGE_MARKER",
  "build_source_cleanup_target",
  "extract_env_key_names",
  "extract_nonempty_sensitive_env_names",
  "extract_source_ref",
  "find_matching_paths",
  "is_v9_build",
  "normalize_posix_path",
  "scan_image_context",
  "summarize_archive_presence",
  "summarize_build_record",
  "validate_upload_file_list",
]
