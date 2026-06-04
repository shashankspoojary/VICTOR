import uvicorn
from config import config

if __name__ == "__main__":
    # Boot the application target "app.main:app"
    # Port and host parameters are read dynamically from configuration settings
    uvicorn.run(
        "app.main:app", 
        host=config.HOST, 
        port=config.PORT, 
        reload=True  # Manual hot-reloading parameters enabled
    )
