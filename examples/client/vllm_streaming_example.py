import asyncio
from vastai import Serverless

MAX_TOKENS = 1024

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-vllm-endpoint")

        system_prompt = (
            "You are Qwen, a helpful AI assistant.\n"
            "You are to only speak in English.\n"
            "Please answer the users response.\n"
            "When you are done, use the <stop> token.\n"
        )


        user_prompt = """
        What is the 118th element in the periodic table?
        """

        payload = {
            "model": "Qwen/Qwen3-8B",
            "prompt" : f"{system_prompt}\n{user_prompt}\n",
            "max_tokens" : MAX_TOKENS,
            "temperature" : 0.8,
            "stop" : ["<stop>"],
            "stream" : True,
        }

        response = await endpoint.request("/v1/completions", payload, cost=MAX_TOKENS, stream=True)
        stream = response["response"]
        async for event in stream:
            print(event["choices"][0]["text"], end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())