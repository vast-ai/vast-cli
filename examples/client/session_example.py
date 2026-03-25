import asyncio
import random
from vastai import Serverless

NUM_SESSIONS = 5


async def run_with_session(endpoint, session_id):
    """Run a single session with one request."""
    session = await endpoint.session(cost=100, lifetime=30)
    try:
        payload = {
            "input": {
                "modifier": "Text2Image",
                "modifications": {
                    "prompt": "Generate a page from a peanuts comic strip.",
                    "width": 512,
                    "height": 512,
                    "steps": 10,
                    "seed": random.randint(1, 1000),
                },
            }
        }
        response = await session.request("/generate/sync", payload, cost=100)
        print(f"[Session {session_id}] {response['response']['output'][0]['local_path']}")
    finally:
        await session.close()


async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-comfy-endpoint")

        # Launch all sessions concurrently and gather results
        await asyncio.gather(*(
            run_with_session(endpoint, i) for i in range(NUM_SESSIONS)
        ))


if __name__ == "__main__":
    asyncio.run(main())
