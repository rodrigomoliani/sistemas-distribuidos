import uvicorn

if __name__ == "__main__":
    uvicorn.run("estoque.api:app", host="0.0.0.0", port=8001)
