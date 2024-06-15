from python:3.11.6-alpine

COPY ./ $HOME/app/

WORKDIR $HOME/app/

RUN pip install Flask
RUN pip install psycopg2-binary
RUN pip install pyjwt
RUN pip install requests
RUN pip install pycryptodome
RUN pip install gunicorn

RUN ["gunicorn", "--bind", "0.0.0.0:5050", "wsgi:app"] # Запуск gunicorn


FROM nginx:1.16.0-alpine
COPY /nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5000
CMD ["nginx", "-g", "daemon off;"]