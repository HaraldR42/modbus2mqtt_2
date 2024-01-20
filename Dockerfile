FROM python:alpine

WORKDIR /app

# upgrade pip to avoid warnings during the docker build
RUN     pip install --root-user-action=ignore --upgrade pip \
    &&  pip install --root-user-action=ignore --no-cache-dir pyserial pymodbus \
    &&  pip install --root-user-action=ignore --no-cache-dir paho-mqtt \
    &&  pip install --root-user-action=ignore --no-cache-dir pyyaml jsons

COPY modbus2mqtt_2.py ./
COPY modbus2mqtt_2 modbus2mqtt_2/

RUN mkdir -p /app/conf/

ENTRYPOINT [ "python", "-u", "./modbus2mqtt_2.py", "--config", "/app/conf/modbus2mqtt_2.yaml" ]