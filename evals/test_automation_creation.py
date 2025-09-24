# import pytest
# from pydantic_ai import Agent


# @pytest.mark.flaky(reruns=3, reruns_delay=2)
# async def test_agent_can_create_reactive_automation(eval_agent: Agent):
#     async with eval_agent:
#         async with eval_agent.run_stream(
#             "Create an automation that sends a Slack message when a flow run fails."
#         ) as result:
#             async for chunk in result.stream_text(delta=True):
#                 print(chunk)
