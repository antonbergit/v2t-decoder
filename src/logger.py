from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProcessingLogger:
    def __init__(self, output_file: Path) -> None:
        self.output_file = output_file
        self.start_time = datetime.now(timezone.utc)
        self.stages: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.input_data: dict[str, Any] = {}
        self.output_data: dict[str, Any] = {}

    def set_input(self, data: dict[str, Any]) -> None:
        self.input_data = data

    def set_output(self, data: dict[str, Any]) -> None:
        self.output_data = data

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def log_stage(
        self,
        name: str,
        status: str,
        *,
        duration_sec: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "name": name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if duration_sec is not None:
            payload["duration_sec"] = duration_sec
        if details:
            payload["details"] = details
        self.stages.append(payload)

    def save(self) -> None:
        end_time = datetime.now(timezone.utc)
        status = "failed" if self.errors else "completed"
        data = {
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration_sec": (end_time - self.start_time).total_seconds(),
            "status": status,
            "input": self.input_data,
            "stages": self.stages,
            "output": self.output_data,
            "warnings": self.warnings,
            "errors": self.errors,
        }
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
