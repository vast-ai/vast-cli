# API docs moved

The OpenAPI spec source files (per-endpoint YAMLs and the build script) have moved to the `vast-ai/docs` repo.

**New location:** [`api-reference/openapi/`](https://github.com/vast-ai/docs/tree/main/api-reference/openapi)

To update the API docs:

1. Edit the relevant file in `vast-ai/docs` at `api-reference/openapi/yaml/<endpoint>.yaml`.
2. From the docs repo root, run `npm run build-openapi` to regenerate `api-reference/openapi.yaml`.
3. Open a PR in `vast-ai/docs`. CI verifies the spec, Mintlify deploys to docs.vast.ai on merge.

See the [docs repo README](https://github.com/vast-ai/docs/blob/main/api-reference/openapi/README.md) for full instructions.
