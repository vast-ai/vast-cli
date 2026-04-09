import asyncio
from deploy import app, generate

async def main():
    print(f"Response: {await generate("Explain quantum computing in one sentence.")}")

if __name__ == "__main__":
    asyncio.run(main())
