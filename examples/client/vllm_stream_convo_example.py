import asyncio
from vastai import Serverless

MAX_TOKENS = 1024

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-vllm-endpoint")

        system_prompt = (
            "You are Qwen.\n"
            "You are to only speak in English.\n"
        )

        user_prompt = "What is the integral of 2x^2 from 0 to 5?"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": "Qwen/Qwen3-8B",
            "messages": messages,
            "stream": True,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.7,
        }

        response = await endpoint.request("/v1/chat/completions", payload, cost=MAX_TOKENS, stream=True)
        stream = response["response"]

        printed_reasoning = False
        printed_answer = False

        async for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})

            rc = delta.get("reasoning_content", None)
            if rc:
                if not printed_reasoning:
                    printed_reasoning = True
                    print("Reasoning:\n", end="", flush=True)
                print(rc, end="", flush=True)

            content = delta.get("content", None)
            if content:
                if not printed_answer:
                    printed_answer = True
                    if printed_reasoning:
                        print("\n\nAnswer:\n", end="", flush=True)
                    else:
                        print("Answer:\n", end="", flush=True)
                print(content, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
