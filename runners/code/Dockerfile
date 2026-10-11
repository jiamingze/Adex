FROM mcr.microsoft.com/playwright/python:v1.55.0-noble
RUN pip install --no-cache-dir playwright==1.55.0
COPY check.py /runner/check.py
USER pwuser
ENTRYPOINT ["python","/runner/check.py"]
