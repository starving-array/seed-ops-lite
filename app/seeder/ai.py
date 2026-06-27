"""AI-assisted data generation strategy using LLMGateway and AI Contract Layer."""

from typing import Any

from pydantic import BaseModel, Field, create_model

from app.llm.contracts.normalizer import AIContractNormalizer
from app.llm.contracts.request import AIContractRequest
from app.llm.gateway import LLMGateway
from app.llm.models import LLMRequest
from app.seeder.exceptions import GenerationException
from app.seeder.models import FieldDefinition
from app.seeder.strategy import BaseStrategy


class AIStrategy(BaseStrategy):
    """Generates synthetic data using AI models via LLMGateway and contracts."""

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize AIStrategy.

        Args:
            gateway: Optional LLMGateway instance.
        """
        self.gateway = gateway or LLMGateway()
        # Store metadata of the last execution for token/cost metrics
        self.last_metadata: Any = None

    async def generate(
        self,
        fields: dict[str, FieldDefinition],
        count: int,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Generate AI fields using the AI contract layer.

        Args:
            fields: Map of field names to FieldDefinition.
            count: Number of records to generate.
            **kwargs: Extra arguments, e.g. "target" table/entity name.

        Returns:
            list[dict[str, Any]]: List of generated records.
        """
        if not fields:
            return [{} for _ in range(count)]

        target = kwargs.get("target", "entity")

        # 1. Build a dynamic Pydantic model for the requested AI fields.
        dynamic_fields = {}
        for name, field_def in fields.items():
            # AI fields are strings
            field_type = str
            desc = f"Realistic synthetic {field_def.type} for field '{name}'."
            if field_def.rules:
                desc += f" Must respect rules: {field_def.rules}"
            dynamic_fields[name] = (field_type, Field(..., description=desc))

        # Dynamically create the Pydantic schema for a single record.
        DynamicRecord = create_model("DynamicRecord", **dynamic_fields)  # type: ignore[call-overload]  # noqa: N806

        # Create a container schema that holds a list of records.
        class AIResponseSchema(BaseModel):
            records: list[DynamicRecord] = Field(  # type: ignore
                ...,
                description=f"List of exactly {count} generated records.",
            )

        # 2. Build the system instruction and prompt for the LLM.
        system_instruction = (
            "You are a synthetic data generation assistant. "
            f"Generate exactly {count} realistic, diverse, and coherent records "
            f"for the target entity '{target}'. "
            "Follow the structural contract exactly."
        )

        prompt_text = (
            f"Generate a list of exactly {count} synthetic records for the target '{target}'.\n"
            "Here are the fields to generate and their rules:\n"
        )
        for name, field_def in fields.items():
            prompt_text += f"- {name}: type={field_def.type}"
            if field_def.rules:
                prompt_text += f", rules={field_def.rules}"
            prompt_text += "\n"
        prompt_text += (
            f"\nPlease generate exactly {count} records, ensuring they are diverse, realistic, and coherent. "
            "Return the results in the requested JSON structure containing the 'records' key."
        )

        # 3. Create the LLMRequest and the AIContractRequest.
        llm_request = LLMRequest(
            prompt=prompt_text,
            system_instruction=system_instruction,
            json_mode=True,
            temperature=kwargs.get("temperature", 0.7),
        )

        contract_request = AIContractRequest[AIResponseSchema](
            prompt=llm_request,
            response_schema=AIResponseSchema,
            json_mode=True,
        )

        # 4. Execute the contract.
        contract_response = await AIContractNormalizer.execute_contract(
            self.gateway, contract_request
        )

        if not contract_response.success:
            err_msg = "Unknown error"
            if contract_response.error:
                err_msg = contract_response.error.message
            raise GenerationException(f"AI Strategy generation failed: {err_msg}")

        # Store metadata for metrics tracking
        self.last_metadata = contract_response.metadata

        # Extract generated records from parsed, validated response
        if contract_response.data and hasattr(contract_response.data, "records"):
            records_data = contract_response.data.records
            records_list = [rec.model_dump() for rec in records_data]  # type: ignore[attr-defined]

            # Adjust list to match count exactly if mismatch occurs
            if len(records_list) < count:
                while len(records_list) < count:
                    if records_list:
                        records_list.append(records_list[-1].copy())
                    else:
                        records_list.append({name: "" for name in fields})
            elif len(records_list) > count:
                records_list = records_list[:count]

            return records_list

        raise GenerationException(
            "AI Strategy returned no data or data in invalid format."
        )
