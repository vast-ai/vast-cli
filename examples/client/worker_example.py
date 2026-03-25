import asyncio
from vastai import Serverless


async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-comfy-endpoint")
        workers = await endpoint.get_workers()
        print(workers)
if __name__ == "__main__":
    asyncio.run(main())