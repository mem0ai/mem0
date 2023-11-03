## Single command to rule them all,

```bash
docker run -d --name embedchain -p 8080:8080 embedchain/app:rest-api-latest
```

### To run the app locally,

```bash
# will help reload on changes
DEVELOPMENT=True && python -m main
```

Using docker (locally),

```bash
docker build -t embedchain/app:rest-api-latest .
docker run -d --name embedchain -p 8080:8080 embedchain/app:rest-api-latest
docker image push embedchain/app:rest-api-latest
```

