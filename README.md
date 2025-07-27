# Repo Exposer

## Build & Run

```
docker build -t repo-exposer .
docker run -p 8000:8000 repo-exposer
```

## Example

```
curl -X POST http://localhost:8000/expose \
    -H "X-API-Key: test123" \
    -H "Content-Type: application/json" \
    -d '{"repo_url":"https://github.com/tiangolo/fastapi","port":9001}'
```
