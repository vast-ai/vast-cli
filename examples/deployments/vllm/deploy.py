from vastai import Deployment
from vastai.data.query import gpu_name, RTX_4090, RTX_5090

app = Deployment(name="vllm")

MODEL = "Qwen/Qwen3-0.6B"

@app.context()
class VLLMEngine:
    async def __aenter__(self):
        from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams

        args = AsyncEngineArgs(model=MODEL, max_model_len=512)
        self.engine = AsyncLLMEngine.from_engine_args(args)
        # Warmup: run a dummy generation to ensure model is fully loaded
        # and KV cache is allocated before serving real requests.
        async for _ in self.engine.generate(
            "warmup", SamplingParams(max_tokens=1), request_id="warmup"
        ):
            pass
        return self

    async def __aexit__(self, *exc):
        self.engine.shutdown_background_loop()


@app.remote(benchmark_dataset=[{"prompt": "Hello"}])
async def generate(prompt: str, max_tokens: int = 128) -> str:
    from vllm import SamplingParams
    import uuid

    engine = app.get_context(VLLMEngine)
    params = SamplingParams(max_tokens=max_tokens, temperature=0.7)
    request_id = str(uuid.uuid4())
    result = None
    async for output in engine.engine.generate(prompt, params, request_id=request_id):
        result = output
    return result.outputs[0].text


image = app.image("vastai/vllm:v0.11.0-cuda-12.8-mvc-cuda-12.0", 32)
image.use_system_python()
image.pip_install("vllm==0.11.0", "transformers==4.57.0")
image.require(gpu_name.in_([RTX_4090, RTX_5090]))
app.configure_autoscaling(min_load=100)
app.ensure_ready()
