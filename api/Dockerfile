FROM python:3.7

RUN mkdir -p /root/.pip/

COPY ./pip.conf /root/.pip/pip.conf

RUN mkdir -p /var/www/html/proxyapi

WORKDIR /var/www/html/proxyapi

ADD . /var/www/html/proxyapi

RUN /usr/local/bin/python -m pip install --upgrade pip

RUN pip install -r requirements

# CMD exec gunicorn  api_service:app -b 0.0.0.0:8426 -w 4 -k uvicorn.workers.UvicornWorker --timeout 30
