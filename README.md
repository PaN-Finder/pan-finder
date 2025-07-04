# Pan-Finder API

## Development

1. Download the all-MiniLM-L12-v2 embedding model from [Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) and place it in the `models` directory.
2. Create a `.env` file in the root directory from the `.env.example` file.
3. Start the development server using Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up
```

## Database

Todo

## Using Frontend (Optional)

(Repository: https://github.com/panosc-eu/searchui)\
Clone the frontend repository somewhere and run it.\
It automatically connects to the PanFinder API server running on [127.0.0.1:8080](http://127.0.0.1:8080).






