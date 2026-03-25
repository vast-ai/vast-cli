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

        try:
            result = await endpoint.request("/v1/completions", payload, cost=MAX_TOKENS, stream=True)
            if result["ok"]:
                # Success path - process the stream
                stream = result["response"]
                async for event in stream:
                    print(event["choices"][0]["text"], end="", flush=True)
            else:
                # Request failed (HTTP error)
                print(f"Request failed. Status={result.get('status')}, Msg={result.get('text')}")
        except Exception as ex:
            # Exception raised (transport error, invalid JSON, etc.)
            print(f"Request failed with exception: {ex}")

if __name__ == "__main__":
    asyncio.run(main())