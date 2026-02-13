import random
import sys

from vastai import Worker, WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig

# ComyUI model configuration
MODEL_SERVER_URL           = 'http://127.0.0.1'
MODEL_SERVER_PORT          = 18288
MODEL_LOG_FILE             = '/var/log/portal/comfyui.log'
MODEL_HEALTHCHECK_ENDPOINT = "/health"

# ComyUI-specific log messages
MODEL_LOAD_LOG_MSG = [
    "To see the GUI go to: "
]

MODEL_ERROR_LOG_MSGS = [
    "MetadataIncompleteBuffer",
    "Value not in list: ",
    "[ERROR] Provisioning Script failed"
]

MODEL_INFO_LOG_MSGS = [
    '"message":"Downloading'
]

benchmark_prompts = [
    "Cartoon hoodie hero; orc, anime cat, bunny; black goo; buff; vector on white.",
    "Cozy farming-game scene with fine details.",
    "2D vector child with soccer ball; airbrush chrome; swagger; antique copper.",
    "Realistic futuristic downtown of low buildings at sunset.",
    "Perfect wave front view; sunny seascape; ultra-detailed water; artful feel.",
    "Clear cup with ice, fruit, mint; creamy swirls; fluid-sim CGI; warm glow.",
    "Male biker with backpack on motorcycle; oilpunk; award-worthy magazine cover.",
    "Collage for textile; surreal cartoon cat in cap/jeans before poster; crisp.",
    "Medieval village inside glass sphere; volumetric light; macro focus.",
    "Iron Man with glowing axe; mecha sci-fi; jungle scene; dynamic light.",
    "Pope Francis DJ in leather jacket, mixing on giant console; dramatic.",
]

benchmark_dataset = [
    {
        "input": {
            "workflow_json": {
                "90": {
                    "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "default"
                    },
                    "class_type": "CLIPLoader",
                    "_meta": {
                    "title": "Load CLIP"
                    }
                },
                "91": {
                    "inputs": {
                    "text": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走，裸露，NSFW",
                    "clip": [
                        "90",
                        0
                    ]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {
                    "title": "CLIP Text Encode (Negative Prompt)"
                    }
                },
                "92": {
                    "inputs": {
                    "vae_name": "wan_2.1_vae.safetensors"
                    },
                    "class_type": "VAELoader",
                    "_meta": {
                    "title": "Load VAE"
                    }
                },
                "93": {
                    "inputs": {
                    "shift": 8.000000000000002,
                    "model": [
                        "101",
                        0
                    ]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {
                    "title": "ModelSamplingSD3"
                    }
                },
                "94": {
                    "inputs": {
                    "shift": 8,
                    "model": [
                        "102",
                        0
                    ]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {
                    "title": "ModelSamplingSD3"
                    }
                },
                "95": {
                    "inputs": {
                    "add_noise": "disable",
                    "noise_seed": 0,
                    "steps": 20,
                    "cfg": 3.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "start_at_step": 10,
                    "end_at_step": 10000,
                    "return_with_leftover_noise": "disable",
                    "model": [
                        "94",
                        0
                    ],
                    "positive": [
                        "99",
                        0
                    ],
                    "negative": [
                        "91",
                        0
                    ],
                    "latent_image": [
                        "96",
                        0
                    ]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {
                    "title": "KSampler (Advanced)"
                    }
                },
                "96": {
                    "inputs": {
                    "add_noise": "enable",
                    "noise_seed": "__RANDOM_INT__",
                    "steps": 20,
                    "cfg": 3.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "start_at_step": 0,
                    "end_at_step": 10,
                    "return_with_leftover_noise": "enable",
                    "model": [
                        "93",
                        0
                    ],
                    "positive": [
                        "99",
                        0
                    ],
                    "negative": [
                        "91",
                        0
                    ],
                    "latent_image": [
                        "104",
                        0
                    ]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {
                    "title": "KSampler (Advanced)"
                    }
                },
                "97": {
                    "inputs": {
                    "samples": [
                        "95",
                        0
                    ],
                    "vae": [
                        "92",
                        0
                    ]
                    },
                    "class_type": "VAEDecode",
                    "_meta": {
                    "title": "VAE Decode"
                    }
                },
                "98": {
                    "inputs": {
                    "filename_prefix": "video/ComfyUI",
                    "format": "auto",
                    "codec": "auto",
                    "video": [
                        "100",
                        0
                    ]
                    },
                    "class_type": "SaveVideo",
                    "_meta": {
                    "title": "Save Video"
                    }
                },
                "99": {
                    "inputs": {
                    "text":prompt,
                    "clip": [
                        "90",
                        0
                    ]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {
                    "title": "CLIP Text Encode (Positive Prompt)"
                    }
                },
                "100": {
                    "inputs": {
                    "fps": 16,
                    "images": [
                        "97",
                        0
                    ]
                    },
                    "class_type": "CreateVideo",
                    "_meta": {
                    "title": "Create Video"
                    }
                },
                "101": {
                    "inputs": {
                    "unet_name": "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                    "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {
                    "title": "Load Diffusion Model"
                    }
                },
                "102": {
                    "inputs": {
                    "unet_name": "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                    "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {
                    "title": "Load Diffusion Model"
                    }
                },
                "104": {
                    "inputs": {
                    "width": 640,
                    "height": 640,
                    "length": 81,
                    "batch_size": 1
                    },
                    "class_type": "EmptyHunyuanLatentVideo",
                    "_meta": {
                    "title": "EmptyHunyuanLatentVideo"
                    }
                }
            }
        }
    } for prompt in benchmark_prompts
]

worker_config = WorkerConfig(
    model_server_url=MODEL_SERVER_URL,
    model_server_port=MODEL_SERVER_PORT,
    model_log_file=MODEL_LOG_FILE,
    model_healthcheck_url=MODEL_HEALTHCHECK_ENDPOINT,
    handlers=[
        HandlerConfig(
            route="/generate/sync",
            allow_parallel_requests=False,
            max_queue_time=10.0,
            benchmark_config=BenchmarkConfig(
                dataset=benchmark_dataset,
                runs=1
            ),
            workload_calculator= lambda _ : 10000.0
        )
    ],
    log_action_config=LogActionConfig(
        on_load=MODEL_LOAD_LOG_MSG,
        on_error=MODEL_ERROR_LOG_MSGS,
        on_info=MODEL_INFO_LOG_MSGS
    )
)

Worker(worker_config).run()