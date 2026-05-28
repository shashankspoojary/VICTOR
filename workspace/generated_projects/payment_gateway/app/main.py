from fastapi import FastAPI

app = FastAPI(title='payment_gateway Microservice')

@app.get('/')
def read_root():
    return {'status': 'online', 'service': 'payment_gateway'}
