import asyncio
from vastai import Serverless
import random

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-comfy-endpoint")

        payload = {
            "a": 1
        }
        
        response = await endpoint.request("/add", payload)

        # Get the file from the path on the local machine using SCP or SFTP
        # or configure S3 to upload to cloud storage.
        print(response["response"]["result"])

if __name__ == "__main__":
    asyncio.run(main())