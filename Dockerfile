# Start by pulling a specific version of the python image
FROM python:3.10-slim
# Set a working directory for the application\
# switch working directory
WORKDIR /app
# copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt


# install the dependencies and packages in the requirements file
RUN apt-get update && apt-get install -y gcc build-essential
RUN apt-get install -y --no-install-recommends bash
RUN pip install -r requirements.txt

# copy every content from the local file to the image
COPY . /app
# Assuming that Slic3r is in the /app/Slic3r directory
RUN chmod -R 777 /app/Slic3r

# configure the container to run in an executed manner
ENTRYPOINT [ "python" ]


# Run the application
CMD ["app.py", "run", "--host=0.0.0.0", "--port=9001"]
