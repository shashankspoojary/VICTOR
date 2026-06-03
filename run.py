import sys
import os
import uvicorn
import config
from app.banner import print_banner

if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    print_banner()
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
