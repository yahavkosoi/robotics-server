from uvicorn import run

if __name__ == "__main__":
    run("server.app:app", host="0.0.0.0", port=8080, reload=True)
