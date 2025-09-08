# Pan‑Finder Kubernetes

The Kubernetes manifests and overlays in this folder are tailored for the European Spallation Source (ESS) environment and this project. They are not intended as generic, portable manifests.

Structure
- `base/` – Baseline manifests.
- `overlays/` – ESS environment overlays

Adapting for other environments
- Copy these manifests and adjust:
	- Image registry/repository and tags.
	- Ingress class/hosts/TLS.
	- Secret names and values (Azure OpenAI, Turnstile, `DATABASE_URL`, etc.).
	- Resource requests/limits and storage classes.
- Review all `ConfigMap`/`Secret` references and environment variables before applying.

Note: Do not commit secrets. Manage them via your cluster’s secret management approach (sealed secrets, external secrets, or per‑cluster manual creation).
