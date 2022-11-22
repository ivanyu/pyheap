# Running

```commandline
poetry run python inferior-simple.py

poetry run flask --app inferior-flask run

poetry run python inferior_django/manage.py runserver

poetry run uvicorn inferior-fastapi:app --reload

poetry run python inferior-sqlalchemy.py

poetry run jupyter-lab
```

These can be run in Docker. Build the image:
```commandline
docker build . -t ivanyu/pyheap-test-inferiors
```

and run with one of the above commands:

```commandline
docker run --rm -ti ivanyu/pyheap-test-inferiors \
  poetry run python inferior-simple.py
```
