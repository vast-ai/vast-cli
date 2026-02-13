import asyncio
from vastai import Serverless

MAX_TOKENS = 128

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-vllm-endpoint")

        payload = {
            "model": "Qwen/Qwen3-8B",
            "prompt" : "Who are you?",
            "max_tokens" : MAX_TOKENS,
            "temperature" : 0.7
        }
        
        response = await endpoint.request("/v1/completions", payload, cost=MAX_TOKENS)
        print(response["response"]["choices"][0]["text"])

if __name__ == "__main__":
    asyncio.run(main())