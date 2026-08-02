from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello from Zahid Hasan Mozumder!"}
