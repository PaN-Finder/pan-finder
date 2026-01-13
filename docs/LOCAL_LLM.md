# Local LLM Setup and Configuration

It is possible to connect to an OpenAI API compatible local LLM server instead of using Azure. 

## Setting up LiteLLM with OLLAMA Models (minimal example)

1. Run Ollama server on your local machine. Load the desired model (e.g., `gemma3:1b`) into Ollama:

```bash
ollama pull gemma3:1b
ollama serve
```

2. Create a configuration file for LiteLLM (`litellm_config.yaml`) with the following content:

```yaml
model_list:
  - model_name: gemma3:1b
    litellm_params:
      model: "ollama_chat/gemma3:1b"
      api_base: "http://host.docker.internal:11434"
      
litellm_settings:
  enable_json_schema_validation: True
```

3. Start the LiteLLM Docker container with the configuration file mounted and the appropriate environment variable set:

```bash
docker run \
    -e OLLAMA_API_BASE="http://host.docker.internal:11434" \
    -v $(pwd)/litellm_config.yaml:/app/config.yaml \
    -p 4001:4000 \
    docker.litellm.ai/berriai/litellm:main-stable \
    --config /app/config.yaml --detailed_debug
```

4. Update the server environment variables in `.env.dev` to point to the LiteLLM server:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY="banana"
OPENAI_BASE_URL="http://host.docker.internal:4001"
DEFAULT_MODEL_NAME=gemma3:1b
EXPLANATION_MODEL_NAME=gemma3:1b
```

5. Run the appliction:

```bash
docker-compose -f docker-compose.dev.yml up --build
```