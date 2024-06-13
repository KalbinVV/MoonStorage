from python:3.11.6-alpine

COPY ./ $HOME/app/

WORKDIR $HOME/app/

RUN pip install Flask
RUN pip install psycopg2-binary
RUN pip install pyjwt
RUN pip install requests

ENTRYPOINT ["python", "api.py"] # Запуск Flask