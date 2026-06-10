import os
import json
import numpy as np
try:
    import face_recognition
except ImportError:
    face_recognition = None

from pathlib import Path
import config

class FaceService:
    def __init__(self):
        self.faces_dir = config.DIRS["workspace_uploads"] / "faces"
        self.faces_file = self.faces_dir / "known_faces.json"
        
        self.faces_dir.mkdir(parents=True, exist_ok=True)
        if not self.faces_file.exists():
            with open(self.faces_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def is_available(self):
        return face_recognition is not None

    def _load_known_faces(self):
        try:
            with open(self.faces_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_known_faces(self, data):
        with open(self.faces_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def identify_face(self, image_path: str):
        if not self.is_available():
            return None
            
        try:
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)
            
            if not face_encodings:
                return {"status": "no_face"}
                
            unknown_encoding = face_encodings[0]
            
            known_data = self._load_known_faces()
            if not known_data:
                return {"status": "unknown"}
                
            known_encodings = []
            known_names = []
            known_rels = []
            
            for key, info in known_data.items():
                known_encodings.append(np.array(info["encoding"]))
                known_names.append(info["name"])
                known_rels.append(info["relationship"])
                
            if not known_encodings:
                return {"status": "unknown"}
                
            results = face_recognition.compare_faces(known_encodings, unknown_encoding)
            
            for i, matched in enumerate(results):
                if matched:
                    return {
                        "status": "known",
                        "name": known_names[i],
                        "relationship": known_rels[i]
                    }
                    
            return {"status": "unknown"}
            
        except Exception as e:
            print(f"Face recognition error: {e}")
            return {"status": "error"}

    def save_face(self, image_path: str, name: str, relationship: str):
        if not self.is_available():
            return False
            
        try:
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)
            
            if not face_encodings:
                return False
                
            encoding = face_encodings[0].tolist()
            
            known_data = self._load_known_faces()
            face_id = f"face_{len(known_data) + 1}"
            
            known_data[face_id] = {
                "name": name,
                "relationship": relationship,
                "encoding": encoding
            }
            
            self._save_known_faces(known_data)
            return True
            
        except Exception as e:
            print(f"Face save error: {e}")
            return False

face_service = FaceService()
