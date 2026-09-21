"""Ordered preprocessing recipes that publish a new dataset version."""

from __future__ import annotations

from ...schemas import TransformRequest, TransformResult
from ..datasets import publish_new_version, read_frame
from .ops import OPERATIONS, apply_step

__all__ = ["OPERATIONS", "apply_step", "run_recipe"]


def run_recipe(dataset_id: str, request: TransformRequest) -> TransformResult:
    frame = read_frame(dataset_id)
    for step in request.steps:
        frame = apply_step(frame, step.operation, step.config)
    result = publish_new_version(dataset_id, frame, request.name, [step.model_dump() for step in request.steps])
    return TransformResult(**result)
