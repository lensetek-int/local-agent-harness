FROM ghcr.io/ggml-org/llama.cpp:server

WORKDIR /app

# Copy model files into container
COPY LFM3-Omni-2B-Q4_K_M.gguf /app/
COPY mmproj-LFM3-Omni-2B-Q8_0.gguf /app/

ENV PORT=8080
ENV HOST=0.0.0.0

EXPOSE 8080

ENTRYPOINT ["llama-server", "-m", "/app/LFM3-Omni-2B-Q4_K_M.gguf", "--mmproj", "/app/mmproj-LFM3-Omni-2B-Q8_0.gguf", "--host", "0.0.0.0", "--port", "8080", "-c", "4096", "--temp", "0.1"]
