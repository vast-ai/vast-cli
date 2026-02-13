from vastai import Serverless
import asyncio


async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-ace-endpoint")

        # ComfyUI API compatible json workflow for ACE Step
        workflow = {
          "14": {
            "inputs": {
              "tags": "funk, pop, soul, rock, melodic, guitar, drums, bass, keyboard, percussion, 105 BPM, energetic, upbeat, groovy, vibrant, dynamic",
              "lyrics": "[verse]\nNeon lights they flicker bright\nCity hums in dead of night\nRhythms pulse through concrete veins\nLost in echoes of refrains\n\n[verse]\nBassline groovin in my chest\nHeartbeats match the citys zest\nElectric whispers fill the air\nSynthesized dreams everywhere\n\n[chorus]\nTurn it up and let it flow\nFeel the fire let it grow\nIn this rhythm we belong\nHear the night sing out our song",
              "lyrics_strength": 0.99,
              "clip": ["40", 1]
            },
            "class_type": "TextEncodeAceStepAudio",
            "_meta": {
              "title": "TextEncodeAceStepAudio"
            }
          },
          "17": {
            "inputs": {
              "seconds": 180,
              "batch_size": 1
            },
            "class_type": "EmptyAceStepLatentAudio",
            "_meta": {
              "title": "EmptyAceStepLatentAudio"
            }
          },
          "18": {
            "inputs": {
              "samples": ["52", 0],
              "vae": ["40", 2]
            },
            "class_type": "VAEDecodeAudio",
            "_meta": {
              "title": "VAE Decode Audio"
            }
          },
          "40": {
            "inputs": {
              "ckpt_name": "ace_step_v1_3.5b.safetensors"
            },
            "class_type": "CheckpointLoaderSimple",
            "_meta": {
              "title": "Load Checkpoint"
            }
          },
          "44": {
            "inputs": {
              "conditioning": ["14", 0]
            },
            "class_type": "ConditioningZeroOut",
            "_meta": {
              "title": "ConditioningZeroOut"
            }
          },
          "49": {
            "inputs": {
              "model": ["51", 0],
              "operation": ["50", 0]
            },
            "class_type": "LatentApplyOperationCFG",
            "_meta": {
              "title": "LatentApplyOperationCFG"
            }
          },
          "50": {
            "inputs": {
              "multiplier": 1.15
            },
            "class_type": "LatentOperationTonemapReinhard",
            "_meta": {
              "title": "LatentOperationTonemapReinhard"
            }
          },
          "51": {
            "inputs": {
              "shift": 6,
              "model": ["40", 0]
            },
            "class_type": "ModelSamplingSD3",
            "_meta": {
              "title": "ModelSamplingSD3"
            }
          },
          "52": {
            "inputs": {
              "seed": "__RANDOM_INT__",
              "steps": 65,
              "cfg": 4,
              "sampler_name": "er_sde",
              "scheduler": "linear_quadratic",
              "denoise": 1,
              "model": ["49", 0],
              "positive": ["14", 0],
              "negative": ["44", 0],
              "latent_image": ["17", 0]
            },
            "class_type": "KSampler",
            "_meta": {
              "title": "KSampler"
            }
          },
          "59": {
            "inputs": {
              "filename_prefix": "audio/ComfyUI",
              "quality": "V0",
              "audioUI": "",
              "audio": ["18", 0]
            },
            "class_type": "SaveAudioMP3",
            "_meta": {
              "title": "Save Audio (MP3)"
            }
          }
        }

        payload = {
          "input": {
            "request_id": "",
            "workflow_json": workflow,
            "s3": {
              "access_key_id": "",
              "secret_access_key": "",
              "endpoint_url": "",
              "bucket_name": "",
              "region": ""
            },
            "webhook": {
              "url": "",
              "extra_params": {
                "user_id": "12345",
                "project_id": "abc-def"
              }
            }
          }
        }

        response = await endpoint.request("/generate/sync", payload)

        # Response contains status, output, and any errors
        print(response["response"])

if __name__ == "__main__":
    asyncio.run(main())