from python:3.11.6-alpine

COPY ./ $HOME/app/

WORKDIR $HOME/app/

RUN pip install Flask
RUN pip install psycopg2-binary

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"] # Запуск FastAPI