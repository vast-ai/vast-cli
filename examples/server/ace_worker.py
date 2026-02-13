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

benchmark_lyrics = [
    "[verse]\nGuardian cloaked in twilight hue\nShadows melt where he breaks through\nEchoes swirl in mystic flight\nHooded hero owns the night\n\n[verse]\nThrough the chaos shapes arise\nFeral whispers, glowing eyes\nOrcs and creatures side by side\nMarch within the inky tide\n\n[chorus]\nRise above the fear and gloom\nLet your courage fully bloom\nIn the darkness stand your ground\nHear the night proclaim your sound",
    "[verse]\nMorning sun on fields of gold\nGentle stories unfold\nEvery breeze a quiet song\nWhere the peaceful hearts belong\n\n[verse]\nLanterns glow at stable doors\nRustling leaves on orchard floors\nSimple joys in every hand\nLife grows soft in fertile land\n\n[chorus]\nLet the day drift slow and free\nRoot your soul where you can be\nIn this haven warm and bright\nFeel the earth breathe pure delight",
    "[verse]\nLittle feet on dusty ground\nChasing dreams without a sound\nSoccer ball in morning light\nHopes take wing in youthful flight\n\n[verse]\nChrome reflections paint the day\nSwagger in the steps that play\nCopper tones in shining air\nChildhood gleaming everywhere\n\n[chorus]\nKick the world with boundless cheer\nHold the magic close and near\nIn each moment bold and true\nLet the sky belong to you",
    "[verse]\nSunset bleeds across the street\nGilded calm in summer heat\nLow-rise towers rimmed with fire\nDreams ignite as lights climb higher\n\n[verse]\nFootsteps scatter through the haze\nFutures shimmer in the blaze\nEvery window tells a tale\nFloating through a tangerine veil\n\n[chorus]\nLet the neon softly glow\nLet your restless heartbeat slow\nIn this city forged in light\nCarry hope into the night",
    "[verse]\nOcean breathes in rolling arcs\nSprays of diamond, glowing sparks\nWaves unfold a perfect line\nNature’s rhythm feels divine\n\n[verse]\nSun above in golden sweep\nPaints the rise of every deep\nShimmer drifting through the blue\nWorld reborn in every view\n\n[chorus]\nLet the tide pull you along\nHear the water’s ancient song\nIn the cresting waves you’ll find\nQuiet peace for heart and mind",
    "[verse]\nGlass aglow with swirling light\nFruits and mints in colors bright\nIcy whispers clink and chime\nFlowing forms suspend in time\n\n[verse]\nCreamy spirals drift within\nGentle currents slowly spin\nWarm reflections lingering sweet\nMixing flavors at your feet\n\n[chorus]\nSip the glow and let it rise\nTaste the sunset in disguise\nIn this moment clear and true\nLet the warmth flow into you",
    "[verse]\nEngines rumble down the lane\nCopper clouds of steam and rain\nOilpunk dreams in metal shine\nRider drifting down the line\n\n[verse]\nLeather jacket, steady glare\nStories sparking in the air\nMagazine lights frame his face\nKing of roads in timeless grace\n\n[chorus]\nThrottle up beyond the bend\nFeel the force of steel ascend\nRide the night and hold on tight\nClaim the world in streaks of light",
    "[verse]\nCut-out shapes in swirling play\nTextures dance in bold array\nCats in denim, grinning wide\nStrut across the patterned tide\n\n[verse]\nPosters hum with neon glow\nSurreal scenes begin to grow\nColors crisp as folded art\nPatchwork beating like a heart\n\n[chorus]\nLet the collage come alive\nWatch the vibrant pieces thrive\nIn this joyful, crafted space\nEvery shape finds its own place",
    "[verse]\nTiny world in crystal glass\nAncient tales behind the mass\nVillage lights in winter gleam\nFrozen in a mystic dream\n\n[verse]\nLantern beams in swirling air\nSoft enchantment everywhere\nShadows drift with gentle grace\nMagic sealed within the space\n\n[chorus]\nHold the sphere and you will see\nEchoes of a memory\nIn the glow of fragile light\nLives a realm of pure delight",
    "[verse]\nArmor hums with power bright\nChopping sparks in jungle night\nMecha spirits shift and scream\nThrough the ferns like shattered beams\n\n[verse]\nAxes blaze in glowing arcs\nLighting up the shadowed marks\nNature roars in trembling air\nClash of steel and cosmic flare\n\n[chorus]\nRaise the fire, strike the ground\nLet your legend shake the sound\nIn the wild where echoes roam\nForge the fight and carve your home",
    "[verse]\nCrowds ignite in vibrant flare\nBeats explode through smoky air\nDJ robes replaced with flame\nPope on decks in holy frame\n\n[verse]\nLeather gleams in blinding light\nTurntables spin with sacred might\nChoirs echo in the bass\nHeaven pulses through the place\n\n[chorus]\nLift the roof and shake the floor\nSacred rhythm evermore\nLet the music take control\nFeel the blessing in your soul",
]

benchmark_dataset = [
    {
        "input": {
            "request_id": "",
            "workflow_json": {
                "14": {
                "inputs": {
                    "tags": "funk, pop, soul, rock, melodic, guitar, drums, bass, keyboard, percussion, 105 BPM, energetic, upbeat, groovy, vibrant, dynamic",
                    "lyrics": lyrics,
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
        }
    } for lyrics in benchmark_lyrics
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
            workload_calculator= lambda _ : 1000.0
        )
    ],
    log_action_config=LogActionConfig(
        on_load=MODEL_LOAD_LOG_MSG,
        on_error=MODEL_ERROR_LOG_MSGS,
        on_info=MODEL_INFO_LOG_MSGS
    )
)

Worker(worker_config).run()