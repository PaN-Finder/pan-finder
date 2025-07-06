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

(Repository: https://github.com/panosc-eu/searchui)<br>
Clone the frontend repository somewhere and run it.<br>
It automatically connects to the PanFinder API server running on [127.0.0.1:8080](http://127.0.0.1:8080).

## Tasks

- [ ] Improve number handling (database) – resolve slow query issue
- [ ] Implement unit handling
- [ ] Use rate limiting vs. CAPTCHA vs. [alternative?]
- [ ] Design frontend interface
- [ ] Add input validation and clarification → Build a dataset that can be used for validation
- [ ] No datasets found → Provide example queries based on input and stored data
- [ ] Allow extracted data to be modified by the client and re-executed
- [ ] Add statistics tracking
- [ ] Implement autocorrect in textarea
- [ ] Add SQL injection protection
- [ ] Implement the ingestor service !!!