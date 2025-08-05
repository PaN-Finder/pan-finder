# Pan-Finder API

## Development

1. Download the all-MiniLM-L12-v2 embedding model from [Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) and place it in the `models` directory.
2. Create a `.env` file in the root directory from the `.env.example` file.
3. Start the development server using Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up
```

## Database

The database can be restored from the Pan-Finder-Poc repository: [pan-finder-poc/backups](https://gitlab.esss.lu.se/swap/pan-finder-poc/-/tree/main/backups?ref_type=heads)

## Using Frontend (Optional)

(Repository: https://github.com/panosc-eu/searchui)<br>
Clone the frontend repository somewhere and run it.<br>
It automatically connects to the PanFinder API server running on [127.0.0.1:8080](http://127.0.0.1:8080).

## Tasks

- [x] Allow extracted data to be modified by the client and re-executed
- [x] Add statistics tracking
- [x] Add feedback functionality
- [ ] Use SQL injection protection
- [ ] Having LLM response in the end of the query (In Progress)
- [ ] Design frontend interface (In progress)
- [ ] Improve number handling (database) – resolve slow query issue
- [ ] Implement unit handling
- [ ] Use rate limiting vs. CAPTCHA vs. Cloudflare Turnstile (https://developers.cloudflare.com/turnstile)
- [ ] Add input validation and clarification → Build a dataset that can be used for validation
- [ ] No datasets found → Provide example queries based on input and stored data
- [ ] Implement autocorrect in textarea
- [ ] Implement the ingestor service !!!

## Temporary docker commands (local development)

Build:
```bash
docker build -f server/docker/Dockerfile.k8s . -t registry.esss.lu.se/swap/pan-finder:server --platform linux/amd64
```
Push:
```bash
docker push registry.esss.lu.se/swap/pan-finder:server
```

Frontend:
```bash
cd searchui
docker build --build-arg API=https://federated.panosc.ess.eu/api --build-arg PAN_FINDER_API=https://pan-finder-api.dev-sims.ess.eu --build-arg TURNSTILE_SITE_KEY=*** -f Dockerfile . -t registry.esss.lu.se/swap/pan-finder:frontend --platform linux/amd64
```

Push Frontend:
```bash
docker push registry.esss.lu.se/swap/pan-finder:frontend
```
