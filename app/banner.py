import sys
import os

# Ensure config is accessible
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import config

def print_banner():
    banner = """

██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗
██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██║   ██║██║██║        ██║   ██║   ██║██████╔╝
╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗
 ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║
  ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝

      Virtual Intelligent Cognitive
          Task-Oriented Resource

    """
    print(banner)
    print("--------------------------------------------------")
    print(f"Assistant Name: {getattr(config, 'ASSISTANT_NAME', 'VICTOR')}")
    print(f"Owner Name:     {getattr(config, 'VICTOR_OWNER_NAME', 'Shashank')}")
    print(f"Host:           {getattr(config, 'HOST', '127.0.0.1')}")
    print(f"Port:           {getattr(config, 'PORT', 8000)}")
    print(f"Groq Model:     {getattr(config, 'GROQ_MODEL', 'qwen/qwen3-32b')}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    print_banner()
