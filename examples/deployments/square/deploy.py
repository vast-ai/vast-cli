from vastai import Deployment
from vastai.data.query import gpu_name, RTX_4090, RTX_5090

app = Deployment(name="square")


@app.remote(benchmark_dataset=[{"x": 2}])
async def square(x):
    return x * x


app.configure_autoscaling(min_load=1000)
image = app.image("vastai/base-image:@vastai-automatic-tag", 16)
image.require(gpu_name.in_([RTX_4090, RTX_5090]))
app.ensure_ready()
