from uuid import uuid4

import pytest
from prefect import flow
from prefect.client.orchestration import get_client


@pytest.mark.usefixtures("prefect_api_url")
async def test_flow_execution_records_state() -> None:
    flow_name = f"scenario-basic-flow-{uuid4().hex[:8]}"

    @flow(name=flow_name)
    def simple_flow() -> str:
        return "done"

    state = simple_flow(return_state=True)
    assert await state.result() == "done"

    flow_run_id = state.state_details.flow_run_id
    assert flow_run_id is not None

    async with get_client() as client:
        flow_obj = await client.read_flow_by_name(flow_name)
        flow_run = await client.read_flow_run(flow_run_id)

    assert flow_obj.name == flow_name
    assert flow_run.flow_id == flow_obj.id
    assert flow_run.state_name == "Completed"
