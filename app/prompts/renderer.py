"""Template renderer engine compiling Jinja2 prompts and registering logs."""

import hashlib
from typing import Any

import jinja2

from app.core.logging.logging import logger
from app.prompts.exceptions import PromptTemplateError
from app.prompts.models import RenderedPrompt
from app.prompts.template import PromptTemplate
from app.telemetry.events import EventID


class PromptRenderer:
    """Jinja2 rendering client for versioned PromptTemplates."""

    @staticmethod
    def render(template: PromptTemplate, variables: dict[str, Any]) -> RenderedPrompt:
        """Render a PromptTemplate and return a RenderedPrompt with a SHA-256 hash.

        Args:
            template: The PromptTemplate to render.
            variables: Input bindings dict.

        Returns:
            RenderedPrompt: Strongly-typed output structures.

        Raises:
            PromptTemplateError: If Jinja2 fails to compile or resolve bindings.
        """
        try:
            # Render system instruction if present
            sys_text = None
            if template.system_template:
                sys_tmpl = jinja2.Template(template.system_template)
                sys_text = sys_tmpl.render(**variables).strip()

            # Render primary prompt body text
            prompt_tmpl = jinja2.Template(template.prompt_template)
            prompt_text = prompt_tmpl.render(**variables).strip()

            # Compute stable SHA-256 fingerprint hash
            # Formed by joining rendered system instructions, prompt body, name, and version
            payload_str = (
                f"{sys_text or ''}:{prompt_text}:{template.name}:{template.version}"
            )
            prompt_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            # Log execution event to telemetry logger
            logger.info(
                EventID.LOG_INFO,
                "Prompt template rendered successfully",
                component="PromptRenderer",
                template_name=template.name,
                template_version=template.version,
                prompt_hash=prompt_hash,
            )

            # Metadata settings
            from datetime import UTC, datetime

            metadata = template.metadata
            provider = metadata.provider if metadata else None
            model = metadata.model if metadata else None
            temperature = metadata.temperature if metadata else 0.0
            max_output_tokens = metadata.max_output_tokens if metadata else 2048
            timeout_seconds = metadata.timeout_seconds if metadata else None
            retry_count = metadata.retry_count if metadata else None
            expected_response = metadata.expected_response if metadata else None
            cacheable = metadata.cacheable if metadata else True
            telemetry_enabled = metadata.telemetry_enabled if metadata else True
            cost_tracking = metadata.cost_tracking if metadata else True
            tags = metadata.tags if metadata else []
            rendered_at = datetime.now(UTC).isoformat()

            # Naive token estimation (approx 4 chars per token)
            prompt_len = len(prompt_text) + (len(sys_text) if sys_text else 0)
            estimated_tokens = max(1, prompt_len // 4)

            return RenderedPrompt(
                system_instruction=sys_text,
                prompt_text=prompt_text,
                template_name=template.name,
                template_version=template.version,
                prompt_hash=prompt_hash,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
                expected_response=expected_response,
                cacheable=cacheable,
                telemetry_enabled=telemetry_enabled,
                cost_tracking=cost_tracking,
                tags=tags,
                rendered_at=rendered_at,
                estimated_tokens=estimated_tokens,
            )

        except Exception as exc:
            raise PromptTemplateError(
                f"Failed to render prompt template '{template.name}' (version: {template.version}): {exc}"
            ) from exc
