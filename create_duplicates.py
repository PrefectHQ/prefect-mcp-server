import time

from prefect import flow


@flow
def test_flow():
    """Simple test flow"""
    print("Running test flow")
    return "completed"


if __name__ == "__main__":
    # Run the flow multiple times with the same custom run name
    for i in range(5):
        print(f"\nRun {i + 1}")
        test_flow.with_options(flow_run_name="test-duplicate")()
        time.sleep(0.5)
