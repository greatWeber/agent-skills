import os
from pathlib import Path


def _load_local_env_file(path: str | Path | None = None) -> None:
	"""Populate missing variables from a simple KEY=VALUE .env file if it exists."""
	env_path = Path(path) if path else Path(__file__).resolve().parent / ".env"
	if not env_path.exists():
		return

	for line in env_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		if "=" not in line:
			continue
		key, value = line.split("=", 1)
		os.environ.setdefault(key.strip(), value.strip())


def _require_env(var_name: str) -> str:
	value = os.getenv(var_name)
	if not value:
		raise RuntimeError(f"Missing environment variable: {var_name}")
	return value

